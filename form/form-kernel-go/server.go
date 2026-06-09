package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

const (
	khTagHeader   int64 = 43001
	khTagRequest  int64 = 43002
	khTagResponse int64 = 43003
	khTagRoute    int64 = 43004
	khTagField    int64 = 43008

	headerFormRouter     = "X-Form-Router"
	headerRouteHow       = "X-Form-Route-How"
	headerRouteWhere     = "X-Form-Route-Where"
	headerRouteWhen      = "X-Form-Route-When"
	headerRouteWho       = "X-Form-Route-Who"
	headerNativeInvite   = "X-Form-Native-Invitation"
	headerNativeState    = "X-Form-Native-Invitation-State"
	headerNativeProtocol = "X-Form-Native-Invitation-Protocol"
	headerNativePath     = "X-Form-Native-Invitation-Selected-Path"
	headerNativeDecline  = "X-Form-Native-Invitation-Decline-Signal"
	headerNativeFallback = "X-Form-Native-Invitation-Decline-Header"
	routeHowNative       = "native-kernel-go"
	routeHowFanout       = "fanout-python"
	nativeInviteValue    = "offered"
	nativeInviteState    = "native-invitation-offered"
	nativeInviteProtocol = "Form/BML route recipe"
	nativeInviteDecline  = "native_invitation_declined"
	maxDecisionHeaderLen = 240
)

var goKernelConfigPath string
var goKernelStartedAt = time.Now().UTC()
var goExternalHTTPClient = &http.Client{}

type volatileCell struct {
	updatedMS int64
	value     Value
}

type volatileCellTable struct {
	mu    sync.Mutex
	cells map[string]volatileCell
}

type pgHandleTable struct {
	mu      sync.Mutex
	next    int64
	handles map[int64]*sql.DB
	lastErr string
}

var goPgHandles = &pgHandleTable{handles: map[int64]*sql.DB{}}
var goVolatileCells = &volatileCellTable{cells: map[string]volatileCell{}}

func volatileCoord(namespace, key string) string {
	return namespace + "\x00" + key
}

func cloneValue(v Value) Value {
	if v.Kind != VList {
		return v
	}
	out := make([]Value, len(v.List))
	for i, item := range v.List {
		out[i] = cloneValue(item)
	}
	v.List = out
	return v
}

func (t *volatileCellTable) put(namespace, key string, value Value) int64 {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.cells[volatileCoord(namespace, key)] = volatileCell{
		updatedMS: time.Now().UnixMilli(),
		value:     cloneValue(value),
	}
	return 1
}

func (t *volatileCellTable) get(namespace, key string) (volatileCell, bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	cell, ok := t.cells[volatileCoord(namespace, key)]
	if ok {
		cell.value = cloneValue(cell.value)
	}
	return cell, ok
}

func (t *volatileCellTable) delete(namespace, key string) bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	coord := volatileCoord(namespace, key)
	_, ok := t.cells[coord]
	if ok {
		delete(t.cells, coord)
	}
	return ok
}

func (t *volatileCellTable) scanSince(namespace string, sinceMS int64) []Value {
	prefix := namespace + "\x00"
	t.mu.Lock()
	defer t.mu.Unlock()
	out := []Value{}
	for coord, cell := range t.cells {
		if !strings.HasPrefix(coord, prefix) || cell.updatedMS < sinceMS {
			continue
		}
		out = append(out, Value{Kind: VList, List: []Value{
			{Kind: VStr, Str: strings.TrimPrefix(coord, prefix)},
			cloneValue(cell.value),
			{Kind: VInt, Int: cell.updatedMS},
		}})
	}
	return out
}

func (t *volatileCellTable) pruneBefore(namespace string, beforeMS int64) int64 {
	prefix := namespace + "\x00"
	t.mu.Lock()
	defer t.mu.Unlock()
	var removed int64
	for coord, cell := range t.cells {
		if strings.HasPrefix(coord, prefix) && cell.updatedMS < beforeMS {
			delete(t.cells, coord)
			removed++
		}
	}
	return removed
}

func (t *pgHandleTable) setErr(err error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if err == nil {
		t.lastErr = ""
	} else {
		t.lastErr = err.Error()
	}
}

func (t *pgHandleTable) register(db *sql.DB) int64 {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.next++
	h := t.next
	t.handles[h] = db
	return h
}

func (t *pgHandleTable) lookup(h int64) (*sql.DB, bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	db, ok := t.handles[h]
	return db, ok
}

func (t *pgHandleTable) close(h int64) bool {
	t.mu.Lock()
	db, ok := t.handles[h]
	if ok {
		delete(t.handles, h)
	}
	t.mu.Unlock()
	if ok {
		_ = db.Close()
	}
	return ok
}

func (k *Kernel) registerHostIONatives() {
	k.registerNative("volatile_cell_put", catCall(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: goVolatileCells.put(args[0].Str, args[1].Str, args[2])}
	})
	k.registerNative("volatile_cell_get", catAccess(), func(_ *Kernel, args []Value) Value {
		cell, ok := goVolatileCells.get(args[0].Str, args[1].Str)
		if !ok {
			return Value{Kind: VNull}
		}
		return cell.value
	})
	k.registerNative("volatile_cell_delete", catCall(), func(_ *Kernel, args []Value) Value {
		if goVolatileCells.delete(args[0].Str, args[1].Str) {
			return Value{Kind: VInt, Int: 1}
		}
		return Value{Kind: VInt, Int: 0}
	})
	k.registerNative("volatile_cell_scan_since", catAccess(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VList, List: goVolatileCells.scanSince(args[0].Str, args[1].Int)}
	})
	k.registerNative("volatile_cell_prune_before", catCall(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: goVolatileCells.pruneBefore(args[0].Str, args[1].Int)}
	})
	k.registerNative("repo_root", catAccess(), func(_ *Kernel, _ []Value) Value {
		root, err := findRepoRoot()
		if err != nil {
			return Value{Kind: VStr, Str: ""}
		}
		return Value{Kind: VStr, Str: root}
	})
	k.registerNative("kernel_runtime_name", catCall(), func(_ *Kernel, _ []Value) Value {
		return Value{Kind: VStr, Str: "form-kernel-go"}
	})
	k.registerNative("kernel_started_unix_ms", catCall(), func(_ *Kernel, _ []Value) Value {
		return Value{Kind: VInt, Int: goKernelStartedAt.UnixMilli()}
	})
	k.registerNative("unix_ms_to_iso_utc", catCall(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VStr, Str: time.UnixMilli(args[0].Int).UTC().Format("2006-01-02T15:04:05Z")}
	})
	k.registerNative("uptime_human", catCall(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VStr, Str: uptimeHuman(args[0].Int)}
	})
	k.registerNative("config_value_or", catCall(), func(_ *Kernel, args []Value) Value {
		config, err := loadKernelConfig()
		if err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VStr, Str: args[1].Str}
		}
		value, ok := lookupConfigPath(config, args[0].Str)
		if !ok {
			return Value{Kind: VStr, Str: args[1].Str}
		}
		switch v := value.(type) {
		case string:
			return Value{Kind: VStr, Str: v}
		case bool:
			return Value{Kind: VBool, Bool: v}
		case float64:
			if v == float64(int64(v)) {
				return Value{Kind: VInt, Int: int64(v)}
			}
			return Value{Kind: VFloat, Float: v}
		case nil:
			return Value{Kind: VStr, Str: args[1].Str}
		default:
			return Value{Kind: VStr, Str: fmt.Sprint(v)}
		}
	})
	k.registerNative("config_database_url", catCall(), func(_ *Kernel, _ []Value) Value {
		url, err := loadConfiguredDatabaseURL()
		if err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VStr, Str: ""}
		}
		return Value{Kind: VStr, Str: url}
	})
	k.registerNative("http_get", catCall(), func(_ *Kernel, args []Value) Value {
		if len(args) < 1 || args[0].Kind != VStr {
			return formHTTPGetResult(0, nil, "", "http_get: url must be a string", 0)
		}
		headers := http.Header{}
		if len(args) > 1 {
			headers = formHTTPHeaderValues(args[1])
		}
		timeout := 10 * time.Second
		if len(args) > 2 {
			timeout = formHTTPTimeout(args[2], timeout)
		}
		return externalHTTPGetValue(args[0].Str, headers, timeout)
	})
	k.registerNative("pg_last_error", catCall(), func(_ *Kernel, _ []Value) Value {
		goPgHandles.mu.Lock()
		defer goPgHandles.mu.Unlock()
		return Value{Kind: VStr, Str: goPgHandles.lastErr}
	})
	k.registerNative("pg_connect", catCall(), func(_ *Kernel, args []Value) Value {
		dsn := strings.TrimSpace(args[0].Str)
		if !strings.HasPrefix(dsn, "postgres://") && !strings.HasPrefix(dsn, "postgresql://") {
			err := fmt.Errorf("pg_connect: database.url is not a PostgreSQL URL")
			goPgHandles.setErr(err)
			return Value{Kind: VInt, Int: -1}
		}
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		db, err := sql.Open("pgx", dsn)
		if err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VInt, Int: -1}
		}
		db.SetMaxOpenConns(8)
		db.SetMaxIdleConns(8)
		db.SetConnMaxLifetime(30 * time.Minute)
		if err := db.PingContext(ctx); err != nil {
			_ = db.Close()
			goPgHandles.setErr(err)
			return Value{Kind: VInt, Int: -1}
		}
		goPgHandles.setErr(nil)
		return Value{Kind: VInt, Int: goPgHandles.register(db)}
	})
	k.registerNative("pg_ping", catCall(), func(_ *Kernel, args []Value) Value {
		db, ok := goPgHandles.lookup(args[0].Int)
		if !ok {
			goPgHandles.setErr(errors.New("pg_ping: unknown connection handle"))
			return Value{Kind: VBool, Bool: false}
		}
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := db.PingContext(ctx); err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VBool, Bool: false}
		}
		goPgHandles.setErr(nil)
		return Value{Kind: VBool, Bool: true}
	})
	k.registerNative("pg_close", catCall(), func(_ *Kernel, args []Value) Value {
		if goPgHandles.close(args[0].Int) {
			return Value{Kind: VInt, Int: 0}
		}
		return Value{Kind: VInt, Int: -1}
	})
	k.registerNative("pg_exec", catCall(), func(_ *Kernel, args []Value) Value {
		db, ok := goPgHandles.lookup(args[0].Int)
		if !ok {
			goPgHandles.setErr(errors.New("pg_exec: unknown connection handle"))
			return Value{Kind: VInt, Int: -1}
		}
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		res, err := db.ExecContext(ctx, args[1].Str, formSQLArgs(args, 2)...)
		if err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VInt, Int: -1}
		}
		n, _ := res.RowsAffected()
		goPgHandles.setErr(nil)
		return Value{Kind: VInt, Int: n}
	})
	k.registerNative("pg_query", catCall(), func(_ *Kernel, args []Value) Value {
		rows, cancel, err := queryRows(args)
		if err != nil {
			if cancel != nil {
				cancel()
			}
			goPgHandles.setErr(err)
			return Value{Kind: VStr, Str: "ERR"}
		}
		defer cancel()
		defer rows.Close()
		cols, err := rows.Columns()
		if err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VStr, Str: "ERR"}
		}
		var out strings.Builder
		rowIndex := 0
		for rows.Next() {
			values, err := scanSQLRow(rows, len(cols))
			if err != nil {
				goPgHandles.setErr(err)
				return Value{Kind: VStr, Str: "ERR"}
			}
			if rowIndex > 0 {
				out.WriteByte('\n')
			}
			for i, v := range values {
				if i > 0 {
					out.WriteByte('\t')
				}
				out.WriteString(formValueString(dbCellToForm(v)))
			}
			rowIndex++
		}
		if err := rows.Err(); err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VStr, Str: "ERR"}
		}
		goPgHandles.setErr(nil)
		return Value{Kind: VStr, Str: out.String()}
	})
	k.registerNative("pg_query_rows", catCall(), func(_ *Kernel, args []Value) Value {
		rows, cancel, err := queryRows(args)
		if err != nil {
			if cancel != nil {
				cancel()
			}
			goPgHandles.setErr(err)
			return Value{Kind: VList, List: []Value{}}
		}
		defer cancel()
		defer rows.Close()
		cols, err := rows.Columns()
		if err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VList, List: []Value{}}
		}
		out := []Value{}
		for rows.Next() {
			values, err := scanSQLRow(rows, len(cols))
			if err != nil {
				goPgHandles.setErr(err)
				return Value{Kind: VList, List: []Value{}}
			}
			row := []Value{{Kind: VStr, Str: "__dict__"}}
			for i, col := range cols {
				row = append(row, Value{Kind: VStr, Str: col}, dbCellToForm(values[i]))
			}
			out = append(out, Value{Kind: VList, List: row})
		}
		if err := rows.Err(); err != nil {
			goPgHandles.setErr(err)
			return Value{Kind: VList, List: []Value{}}
		}
		goPgHandles.setErr(nil)
		return Value{Kind: VList, List: out}
	})
}

func queryRows(args []Value) (*sql.Rows, context.CancelFunc, error) {
	db, ok := goPgHandles.lookup(args[0].Int)
	if !ok {
		return nil, nil, errors.New("pg_query_rows: unknown connection handle")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	rows, err := db.QueryContext(ctx, args[1].Str, formSQLArgs(args, 2)...)
	if err != nil {
		cancel()
		return nil, nil, err
	}
	return rows, cancel, nil
}

func formSQLArgs(args []Value, idx int) []any {
	if len(args) <= idx || args[idx].Kind != VList {
		return nil
	}
	out := make([]any, 0, len(args[idx].List))
	for _, v := range args[idx].List {
		switch v.Kind {
		case VInt:
			out = append(out, v.Int)
		case VFloat:
			out = append(out, v.Float)
		case VBool:
			out = append(out, v.Bool)
		case VStr:
			out = append(out, v.Str)
		case VNull:
			out = append(out, nil)
		default:
			out = append(out, formValueString(v))
		}
	}
	return out
}

const maxHTTPGetBodyBytes int64 = 25 << 20

func externalHTTPGetValue(rawURL string, headers http.Header, timeout time.Duration) Value {
	start := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return formHTTPGetResult(0, nil, "", err.Error(), time.Since(start).Milliseconds())
	}
	for key, vals := range headers {
		if hopByHopHeader(key) {
			continue
		}
		for _, val := range vals {
			req.Header.Add(key, val)
		}
	}

	resp, err := goExternalHTTPClient.Do(req)
	if err != nil {
		return formHTTPGetResult(0, nil, "", err.Error(), time.Since(start).Milliseconds())
	}
	defer resp.Body.Close()

	bodyBytes, readErr := io.ReadAll(io.LimitReader(resp.Body, maxHTTPGetBodyBytes+1))
	errorText := ""
	if readErr != nil {
		errorText = readErr.Error()
	}
	if int64(len(bodyBytes)) > maxHTTPGetBodyBytes {
		bodyBytes = bodyBytes[:maxHTTPGetBodyBytes]
		errorText = fmt.Sprintf("http_get: response body exceeded %d bytes", maxHTTPGetBodyBytes)
	}
	return formHTTPGetResult(resp.StatusCode, resp.Header, string(bodyBytes), errorText, time.Since(start).Milliseconds())
}

func formHTTPHeaderValues(v Value) http.Header {
	headers := http.Header{}
	if v.Kind != VList {
		return headers
	}
	for _, raw := range v.List {
		if raw.Kind != VList || len(raw.List) != 3 {
			continue
		}
		if raw.List[0].Kind != VInt || raw.List[0].Int != khTagHeader ||
			raw.List[1].Kind != VStr || raw.List[2].Kind != VStr {
			continue
		}
		name := strings.TrimSpace(raw.List[1].Str)
		if name == "" {
			continue
		}
		headers.Add(name, raw.List[2].Str)
	}
	return headers
}

func formHTTPTimeout(v Value, fallback time.Duration) time.Duration {
	var ms int64
	switch v.Kind {
	case VInt:
		ms = v.Int
	case VFloat:
		ms = int64(v.Float)
	default:
		return fallback
	}
	if ms <= 0 {
		return fallback
	}
	timeout := time.Duration(ms) * time.Millisecond
	if timeout > 60*time.Second {
		return 60 * time.Second
	}
	return timeout
}

func formHTTPGetResult(status int, headers http.Header, body, errorText string, durationMS int64) Value {
	return Value{Kind: VList, List: []Value{
		{Kind: VStr, Str: "__dict__"},
		{Kind: VStr, Str: "status_code"},
		{Kind: VInt, Int: int64(status)},
		{Kind: VStr, Str: "body"},
		{Kind: VStr, Str: body},
		{Kind: VStr, Str: "error"},
		{Kind: VStr, Str: errorText},
		{Kind: VStr, Str: "duration_ms"},
		{Kind: VInt, Int: durationMS},
		{Kind: VStr, Str: "headers"},
		{Kind: VList, List: formHTTPHeaderList(headers)},
	}}
}

func formHTTPHeaderList(headers http.Header) []Value {
	if headers == nil {
		return []Value{}
	}
	keys := make([]string, 0, len(headers))
	for key := range headers {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	out := []Value{}
	for _, key := range keys {
		values := append([]string{}, headers[key]...)
		sort.Strings(values)
		for _, value := range values {
			out = append(out, Value{Kind: VList, List: []Value{
				{Kind: VInt, Int: khTagHeader},
				{Kind: VStr, Str: key},
				{Kind: VStr, Str: value},
			}})
		}
	}
	return out
}

func scanSQLRow(rows *sql.Rows, n int) ([]any, error) {
	values := make([]any, n)
	dest := make([]any, n)
	for i := range values {
		dest[i] = &values[i]
	}
	if err := rows.Scan(dest...); err != nil {
		return nil, err
	}
	return values, nil
}

func dbCellToForm(v any) Value {
	switch x := v.(type) {
	case nil:
		return Value{Kind: VNull}
	case int64:
		return Value{Kind: VInt, Int: x}
	case int32:
		return Value{Kind: VInt, Int: int64(x)}
	case int:
		return Value{Kind: VInt, Int: int64(x)}
	case float64:
		return Value{Kind: VFloat, Float: x}
	case float32:
		return Value{Kind: VFloat, Float: float64(x)}
	case bool:
		return Value{Kind: VBool, Bool: x}
	case string:
		return Value{Kind: VStr, Str: x}
	case []byte:
		return Value{Kind: VStr, Str: string(x)}
	case time.Time:
		return Value{Kind: VStr, Str: x.UTC().Format(time.RFC3339Nano)}
	default:
		return Value{Kind: VStr, Str: fmt.Sprint(x)}
	}
}

func formValueString(v Value) string {
	switch v.Kind {
	case VStr:
		return v.Str
	case VInt:
		return strconv.FormatInt(v.Int, 10)
	case VFloat:
		return formatFloatJS(v.Float)
	case VBool:
		if v.Bool {
			return "true"
		}
		return "false"
	case VNull:
		return ""
	default:
		return v.String()
	}
}

func loadConfiguredDatabaseURL() (string, error) {
	config, err := loadKernelConfig()
	if err != nil {
		return "", err
	}
	if db, ok := config["database"].(map[string]any); ok {
		if url, ok := db["url"].(string); ok && strings.TrimSpace(url) != "" {
			return strings.TrimSpace(url), nil
		}
	}
	if url, ok := config["database_url"].(string); ok && strings.TrimSpace(url) != "" {
		return strings.TrimSpace(url), nil
	}
	return "", errors.New("database.url is not configured")
}

func lookupConfigPath(config map[string]any, path string) (any, bool) {
	current := any(config)
	for _, part := range strings.Split(path, ".") {
		if part == "" {
			return nil, false
		}
		obj, ok := current.(map[string]any)
		if !ok {
			return nil, false
		}
		current, ok = obj[part]
		if !ok {
			return nil, false
		}
	}
	return current, true
}

func uptimeHuman(seconds int64) string {
	if seconds < 0 {
		seconds = 0
	}
	days := seconds / 86400
	remainder := seconds % 86400
	hours := remainder / 3600
	remainder %= 3600
	minutes := remainder / 60
	secs := remainder % 60
	if days > 0 {
		return fmt.Sprintf("%dd %dh %dm %ds", days, hours, minutes, secs)
	}
	if hours > 0 {
		return fmt.Sprintf("%dh %dm %ds", hours, minutes, secs)
	}
	if minutes > 0 {
		return fmt.Sprintf("%dm %ds", minutes, secs)
	}
	return fmt.Sprintf("%ds", secs)
}

func loadKernelConfig() (map[string]any, error) {
	root, err := findRepoRoot()
	if err != nil {
		return nil, err
	}
	merged := map[string]any{}
	base := filepath.Join(root, "api", "config", "api.json")
	if err := mergeConfigFile(merged, base); err != nil {
		return nil, err
	}
	overlay := goKernelConfigPath
	if overlay == "" {
		if home, err := os.UserHomeDir(); err == nil {
			overlay = filepath.Join(home, ".coherence-network", "config.json")
		}
	}
	if overlay != "" {
		_ = mergeConfigFile(merged, overlay)
	}
	if home, err := os.UserHomeDir(); err == nil {
		mergeKernelKeys(merged, filepath.Join(home, ".coherence-network", "keys.json"))
	}
	return merged, nil
}

func mergeKernelKeys(dst map[string]any, path string) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return
	}
	var keys map[string]any
	if err := json.Unmarshal(bytes, &keys); err != nil {
		return
	}
	dst["keys"] = keys
	if token := githubTokenFromKeys(keys); token != "" {
		if current, ok := dst["github_token"].(string); !ok || strings.TrimSpace(current) == "" {
			dst["github_token"] = token
		}
	}
}

func githubTokenFromKeys(keys map[string]any) string {
	if github, ok := keys["github"].(map[string]any); ok {
		for _, key := range []string{"token", "api_token"} {
			if value, ok := github[key].(string); ok && strings.TrimSpace(value) != "" {
				return strings.TrimSpace(value)
			}
		}
	}
	if value, ok := keys["github_token"].(string); ok && strings.TrimSpace(value) != "" {
		return strings.TrimSpace(value)
	}
	return ""
}

func mergeConfigFile(dst map[string]any, path string) error {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var src map[string]any
	if err := json.Unmarshal(bytes, &src); err != nil {
		return err
	}
	deepMerge(dst, src)
	return nil
}

func deepMerge(dst, src map[string]any) {
	for k, v := range src {
		if sv, ok := v.(map[string]any); ok {
			if dv, ok := dst[k].(map[string]any); ok {
				deepMerge(dv, sv)
				continue
			}
		}
		dst[k] = v
	}
}

func findRepoRoot() (string, error) {
	wd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		if _, err := os.Stat(filepath.Join(wd, "api", "config", "api.json")); err == nil {
			return wd, nil
		}
		next := filepath.Dir(wd)
		if next == wd {
			break
		}
		wd = next
	}
	return "", errors.New("could not find repo root containing api/config/api.json")
}

type goRoute struct {
	name           string
	method         string
	path           string
	handlerName    string
	requiredHeader string
	pressureBudget int64
	handler        *Closure
	typedRequest   bool
}

type goServeProgram struct {
	source   string
	artifact []byte
	upstream *url.URL
	client   *http.Client
	pool     sync.Pool
}

type goServeWorker struct {
	k       *Kernel
	env     *Frame
	routes  []goRoute
	program *goServeProgram
}

type sourcePart struct {
	label  string
	source string
}

var sourceCompileMu sync.Mutex

var sourceCompilePreludes = []string{
	"form-ontology-loader.fk",
	"line-grammar.fk",
	"bmf-core.fk",
	"bmf-grammar.fk",
	"bml.fk",
	"bml-source.fk",
	"source-compiler.fk",
}

var sourceRouteLanguagePreludes = []string{
	"json.fk",
	"core.fk",
	"sha256.fk",
	"kernel-http.fk",
	"language-model.fk",
}

func joinSourceParts(parts []sourcePart) string {
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		out = append(out, part.source)
	}
	return strings.Join(out, "\n")
}

func manifestHasSourceSections(src string) bool {
	for _, line := range strings.Split(src, "\n") {
		if strings.HasPrefix(strings.TrimLeft(line, " \t"), "section [") {
			return true
		}
	}
	return false
}

func normalizeFormStdlibDir(stdlibDir string) (string, error) {
	stdlibAbs, err := filepath.Abs(stdlibDir)
	if err != nil {
		return "", fmt.Errorf("--stdlib %s: %w", stdlibDir, err)
	}
	if real, err := filepath.EvalSymlinks(stdlibAbs); err == nil {
		stdlibAbs = real
	}
	if filepath.Base(stdlibAbs) != "form-stdlib" {
		return "", fmt.Errorf("--stdlib must point at a directory named form-stdlib; got %s", stdlibAbs)
	}
	return stdlibAbs, nil
}

func defaultFormStdlibDir() (string, error) {
	root, err := findRepoRoot()
	if err != nil {
		return "", err
	}
	return normalizeFormStdlibDir(filepath.Join(root, "form", "form-stdlib"))
}

func sourceCompileServeProgram(parts []sourcePart, stdlibDir string) ([]byte, error) {
	sourceCompileMu.Lock()
	defer sourceCompileMu.Unlock()

	stdlibAbs, err := normalizeFormStdlibDir(stdlibDir)
	if err != nil {
		return nil, err
	}
	stdlibParent := filepath.Dir(stdlibAbs)
	prevCwd, err := os.Getwd()
	if err != nil {
		return nil, fmt.Errorf("read cwd: %w", err)
	}
	if err := os.Chdir(stdlibParent); err != nil {
		return nil, fmt.Errorf("chdir %s: %w", stdlibParent, err)
	}
	defer func() { _ = os.Chdir(prevCwd) }()

	k := NewKernel()
	roots := []NodeID{}
	for _, name := range sourceRouteLanguagePreludes {
		path := filepath.Join(stdlibAbs, name)
		source, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("route-language prelude %s: %w", path, err)
		}
		if err := compileRouteSourceIntoRecipe(k, &roots, path, string(source), stdlibAbs); err != nil {
			return nil, err
		}
	}
	for _, part := range parts {
		if err := compileRouteSourceIntoRecipe(k, &roots, part.label, part.source, stdlibAbs); err != nil {
			return nil, err
		}
	}
	if len(roots) == 0 {
		return nil, errors.New("source manifest produced no recipe roots")
	}
	root := roots[0]
	if len(roots) > 1 {
		root = k.intern(catBlock(RBlockDo), roots)
	}
	return serializeArtifact(k, root), nil
}

func sourceCompileDriver(stdlibAbs, body string) (string, error) {
	parts := make([]string, 0, len(sourceCompilePreludes)+1)
	for _, name := range sourceCompilePreludes {
		path := filepath.Join(stdlibAbs, name)
		source, err := os.ReadFile(path)
		if err != nil {
			return "", fmt.Errorf("read source-compile prelude %s: %w", path, err)
		}
		parts = append(parts, string(source))
	}
	parts = append(parts, body)
	return strings.Join(parts, "\n"), nil
}

func compileSourceSectionToRecipeNode(dialectName, body, stdlibAbs string) (outKernel *Kernel, outRoot NodeID, outErr error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			outKernel = nil
			outRoot = NodeID{}
			outErr = fmt.Errorf("source compiler panic: %v", recovered)
		}
	}()
	driverBody := fmt.Sprintf(
		"(fsc-compile-section-recipe %s %s)",
		sexpStringLiteral(dialectName),
		sexpStringLiteral(body),
	)
	driverSource, err := sourceCompileDriver(stdlibAbs, driverBody)
	if err != nil {
		return nil, NodeID{}, err
	}
	k := NewKernel()
	root := readRootFromSource(k, driverSource)
	env := NewFrame(nil)
	k.activeRoots = []NodeID{root}
	value := k.walk(root, env)
	if value.Kind != VNodeID {
		return nil, NodeID{}, errors.New("source compiler did not return a recipe NodeID")
	}
	return k, value.Nid, nil
}

func importRecipeLeaf(dst, src *Kernel, nid NodeID) NodeID {
	if nid.Level != LevelTrivial {
		return nid
	}
	switch nid.Type {
	case TrivInt:
		return dst.internTrivialInt(int64(int32(nid.Inst)))
	case TrivString:
		return dst.internString(src.nameStr(NameID(nid.Inst)))
	case TrivBool, TrivNull:
		return nid
	case TrivFloat32:
		return dst.internTrivialFloat32(src.decodeFloat32(nid.Inst))
	case TrivFloat64:
		return dst.internTrivialFloat64(src.decodeFloat64(nid.Inst))
	default:
		return nid
	}
}

func importRecipeNode(dst, src *Kernel, nid NodeID, memo map[NodeID]NodeID) NodeID {
	if imported, ok := memo[nid]; ok {
		return imported
	}
	var imported NodeID
	if recipe, ok := src.byID[nid]; ok {
		category := importRecipeNode(dst, src, recipe.Category, memo)
		children := make([]NodeID, len(recipe.Children))
		for i, child := range recipe.Children {
			children[i] = importRecipeNode(dst, src, child, memo)
		}
		imported = dst.intern(category, children)
	} else {
		imported = importRecipeLeaf(dst, src, nid)
	}
	memo[nid] = imported
	importSourceAttribution(dst, src, nid, imported)
	return imported
}

func importRecipeFrom(dst, src *Kernel, root NodeID) NodeID {
	return importRecipeNode(dst, src, root, map[NodeID]NodeID{})
}

func importSourceAttribution(dst, src *Kernel, srcNid, dstNid NodeID) {
	loc, ok := src.sourceAttr[srcNid]
	if !ok {
		return
	}
	file := ""
	if int(loc.FileID) < len(src.strs) {
		file = src.strs[loc.FileID]
	}
	fileNid := dst.internString(file)
	dst.sourceAttr[dstNid] = sourceLoc{
		FileID: NameID(fileNid.Inst),
		Line:   loc.Line,
		Col:    loc.Col,
	}
	dst.framebufferRoots = append(dst.framebufferRoots, dstNid)
}

func pinRuntimeCompiledRoot(k *Kernel, root NodeID, label string) {
	if label == "" {
		label = "runtime:string"
	}
	if _, ok := k.sourceAttr[root]; !ok {
		fileNid := k.internString(label)
		k.sourceAttr[root] = sourceLoc{FileID: NameID(fileNid.Inst), Line: 1, Col: 1}
		k.framebufferRoots = append(k.framebufferRoots, root)
	}
	k.activeRoots = append(k.activeRoots, root)
}

func compileSourceSectionIntoKernel(dst *Kernel, dialectName, body, label string) (NodeID, error) {
	stdlibAbs, err := defaultFormStdlibDir()
	if err != nil {
		return NodeID{}, err
	}
	sourceCompileMu.Lock()
	defer sourceCompileMu.Unlock()
	sectionKernel, sectionRoot, err := compileSourceSectionToRecipeNode(dialectName, body, stdlibAbs)
	if err != nil {
		return NodeID{}, err
	}
	imported := importRecipeFrom(dst, sectionKernel, sectionRoot)
	pinRuntimeCompiledRoot(dst, imported, label)
	return imported, nil
}

func compileSourceTextIntoKernel(dst *Kernel, sourceLabel, src string) (NodeID, error) {
	stdlibAbs, err := defaultFormStdlibDir()
	if err != nil {
		return NodeID{}, err
	}
	sourceCompileMu.Lock()
	defer sourceCompileMu.Unlock()
	sectionKernel := NewKernel()
	roots := []NodeID{}
	if err := compileRouteSourceIntoRecipe(sectionKernel, &roots, sourceLabel, src, stdlibAbs); err != nil {
		return NodeID{}, err
	}
	if len(roots) == 0 {
		return NodeID{}, errors.New("source compiler produced no recipe roots")
	}
	root := roots[0]
	if len(roots) > 1 {
		root = sectionKernel.intern(catBlock(RBlockDo), roots)
	}
	imported := importRecipeFrom(dst, sectionKernel, root)
	pinRuntimeCompiledRoot(dst, imported, sourceLabel)
	return imported, nil
}

func sourceLineNext(src string, i int) int {
	if off := strings.IndexByte(src[i:], '\n'); off >= 0 {
		return i + off + 1
	}
	return len(src)
}

func sourceLineEnd(src string, i int) int {
	if off := strings.IndexByte(src[i:], '\n'); off >= 0 {
		return i + off
	}
	return len(src)
}

func findSectionFrom(src string, i int) int {
	for i < len(src) {
		end := sourceLineEnd(src, i)
		line := src[i:end]
		trimmed := strings.TrimLeft(line, " \t")
		if strings.HasPrefix(trimmed, "section [") {
			return i + len(line) - len(trimmed)
		}
		i = sourceLineNext(src, i)
	}
	return -1
}

func findSectionClose(src string, bodyStart int) (int, error) {
	depth := 0
	for i := bodyStart; i < len(src); {
		end := sourceLineEnd(src, i)
		line := strings.TrimSpace(src[i:end])
		if line == "}" {
			if depth == 0 {
				return i, nil
			}
			depth--
		} else if strings.HasSuffix(line, "{") {
			depth++
		}
		i = sourceLineNext(src, i)
	}
	return -1, errors.New("source-compile: unterminated section block")
}

func countTopLevelTokens(toks []sexpToken) int {
	depth := 0
	count := 0
	for _, t := range toks {
		switch t.kind {
		case "LPAREN":
			if depth == 0 {
				count++
			}
			depth++
		case "RPAREN":
			depth--
		default:
			if depth == 0 {
				count++
			}
		}
	}
	return count
}

func parseRawRouteSegment(k *Kernel, roots *[]NodeID, src string) {
	toks := tokenizeSexp(src)
	if len(toks) == 0 {
		return
	}
	var root NodeID
	if countTopLevelTokens(toks) == 1 {
		var next int
		root, next = k.readSexpr(toks, 0)
		_ = next
	} else {
		root = readRootFromSource(k, fmt.Sprintf("(do %s)", src))
	}
	*roots = append(*roots, root)
}

func compileRouteSourceIntoRecipe(k *Kernel, roots *[]NodeID, sourceLabel, src, stdlibAbs string) error {
	cursor := 0
	for {
		sectionPos := findSectionFrom(src, cursor)
		if sectionPos < 0 {
			break
		}
		parseRawRouteSegment(k, roots, src[cursor:sectionPos])
		dialectStart := sectionPos + len("section [")
		dialectRelEnd := strings.IndexByte(src[dialectStart:], ']')
		if dialectRelEnd < 0 {
			return fmt.Errorf("source-compile: %s section missing ]", sourceLabel)
		}
		dialectEnd := dialectStart + dialectRelEnd
		openRel := strings.IndexByte(src[dialectEnd:], '{')
		if openRel < 0 {
			return fmt.Errorf("source-compile: %s section missing {", sourceLabel)
		}
		open := dialectEnd + openRel
		close, err := findSectionClose(src, open+1)
		if err != nil {
			return fmt.Errorf("%s: %w", sourceLabel, err)
		}
		dialectName := strings.TrimSpace(src[dialectStart:dialectEnd])
		body := src[open+1 : close]
		sectionKernel, sectionRoot, err := compileSourceSectionToRecipeNode(dialectName, body, stdlibAbs)
		if err != nil {
			return fmt.Errorf("source-compile: %s [%s]: %w", sourceLabel, dialectName, err)
		}
		*roots = append(*roots, importRecipeFrom(k, sectionKernel, sectionRoot))
		cursor = sourceLineNext(src, close)
	}
	parseRawRouteSegment(k, roots, src[cursor:])
	return nil
}

func sexpStringLiteral(s string) string {
	var b strings.Builder
	b.Grow(len(s) + 2)
	b.WriteByte('"')
	for _, ch := range s {
		switch ch {
		case '\\':
			b.WriteString("\\\\")
		case '"':
			b.WriteString("\\\"")
		case '\n':
			b.WriteString("\\n")
		case '\t':
			b.WriteString("\\t")
		case '\r':
			b.WriteString("\\r")
		default:
			b.WriteRune(ch)
		}
	}
	b.WriteByte('"')
	return b.String()
}

func cliServe(args []string) int {
	port := 18080
	stdlibDir := "form-stdlib"
	var upstream *url.URL
	files := []string{}
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--port":
			i++
			if i >= len(args) {
				fmt.Fprintln(os.Stderr, "serve --port requires a value")
				return 2
			}
			n, err := strconv.Atoi(args[i])
			if err != nil || n <= 0 {
				fmt.Fprintf(os.Stderr, "invalid port %q\n", args[i])
				return 2
			}
			port = n
		case "--config":
			i++
			if i >= len(args) {
				fmt.Fprintln(os.Stderr, "serve --config requires a path")
				return 2
			}
			goKernelConfigPath = args[i]
		case "--stdlib":
			i++
			if i >= len(args) {
				fmt.Fprintln(os.Stderr, "serve --stdlib requires a directory")
				return 2
			}
			stdlibDir = args[i]
		case "--upstream":
			i++
			if i >= len(args) {
				fmt.Fprintln(os.Stderr, "serve --upstream requires a value")
				return 2
			}
			parsed, err := url.Parse(args[i])
			if err != nil || parsed.Scheme == "" || parsed.Host == "" {
				fmt.Fprintf(os.Stderr, "invalid upstream %q\n", args[i])
				return 2
			}
			upstream = parsed
		default:
			files = append(files, args[i])
		}
	}
	if len(files) == 0 {
		fmt.Fprintln(os.Stderr, "usage: form-kernel-go serve --port 18080 [--config path] [--upstream https://api.example] <route-prelude.fk...>")
		return 2
	}
	parts := make([]sourcePart, 0, len(files))
	for _, path := range files {
		bytes, err := os.ReadFile(path)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read %s: %v\n", path, err)
			return 1
		}
		parts = append(parts, sourcePart{label: path, source: string(bytes)})
	}
	program := &goServeProgram{
		source:   joinSourceParts(parts),
		upstream: upstream,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
	if manifestHasSourceSections(program.source) {
		artifact, err := sourceCompileServeProgram(parts, stdlibDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "serve source compile: %v\n", err)
			return 1
		}
		program.source = ""
		program.artifact = artifact
		fmt.Fprintf(os.Stderr, "form-kernel-go serve: source manifest compiled via %s to Form recipe object\n", stdlibDir)
	}
	program.pool.New = func() any {
		worker, err := buildGoServeWorker(program)
		if err != nil {
			panic(err)
		}
		return worker
	}
	first, err := buildGoServeWorker(program)
	if err != nil {
		fmt.Fprintf(os.Stderr, "serve route load: %v\n", err)
		return 1
	}
	program.pool.Put(first)
	mux := http.NewServeMux()
	mux.Handle("/", program)
	addr := fmt.Sprintf("127.0.0.1:%d", port)
	fmt.Fprintf(os.Stderr, "form-kernel-go serve listening on http://%s\n", addr)
	server := &http.Server{
		Addr:              addr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		fmt.Fprintf(os.Stderr, "serve: %v\n", err)
		return 1
	}
	return 0
}

func buildGoServeWorker(program *goServeProgram) (*goServeWorker, error) {
	k := NewKernel()
	var root NodeID
	if len(program.artifact) > 0 {
		imported, err := deserializeArtifact(k, program.artifact)
		if err != nil {
			return nil, err
		}
		root = imported
	} else {
		root = readRootFromSource(k, program.source)
	}
	env := NewFrame(nil)
	k.activeRoots = []NodeID{root}
	_ = k.walk(root, env)
	routes, err := buildGoRoutes(k, env)
	if err != nil {
		return nil, err
	}
	return &goServeWorker{k: k, env: env, routes: routes, program: program}, nil
}

func buildGoRoutes(k *Kernel, env *Frame) ([]goRoute, error) {
	routesID := NameID(k.internString("routes").Inst)
	routesValue, ok := env.Lookup(routesID)
	if !ok || routesValue.Kind != VList {
		return nil, errors.New("route program must bind a top-level routes list")
	}
	out := make([]goRoute, 0, len(routesValue.List))
	for _, row := range routesValue.List {
		route, err := buildGoRoute(k, env, row)
		if err != nil {
			return nil, err
		}
		out = append(out, route)
	}
	return out, nil
}

func buildGoRoute(k *Kernel, env *Frame, row Value) (goRoute, error) {
	if row.Kind != VList {
		return goRoute{}, errors.New("each route must be a kh-route row or compatibility path/handler row")
	}
	if len(row.List) == 8 && row.List[0].Kind == VInt && row.List[0].Int == khTagRoute {
		return buildKHRoute(k, env, row.List)
	}
	if len(row.List) == 2 {
		if row.List[0].Kind != VStr || row.List[1].Kind != VClosure {
			return goRoute{}, errors.New("compatibility route row must be (list path handler)")
		}
		return goRoute{
			name:           row.List[0].Str,
			method:         "ANY",
			path:           row.List[0].Str,
			handlerName:    k.nameStr(row.List[1].Cl.Name),
			pressureBudget: 40,
			handler:        row.List[1].Cl,
		}, nil
	}
	if len(row.List) == 3 {
		if row.List[0].Kind != VStr || row.List[1].Kind != VStr || row.List[2].Kind != VClosure {
			return goRoute{}, errors.New("compatibility route row must be (list method path handler)")
		}
		return goRoute{
			name:           row.List[1].Str,
			method:         row.List[0].Str,
			path:           row.List[1].Str,
			handlerName:    k.nameStr(row.List[2].Cl.Name),
			pressureBudget: 40,
			handler:        row.List[2].Cl,
		}, nil
	}
	return goRoute{}, errors.New("each route must be a kh-route row or compatibility path/handler row")
}

func buildKHRoute(k *Kernel, env *Frame, fields []Value) (goRoute, error) {
	name, err := routeString(fields[1], "name")
	if err != nil {
		return goRoute{}, err
	}
	method, err := routeString(fields[2], "method")
	if err != nil {
		return goRoute{}, err
	}
	path, err := routeString(fields[3], "pattern")
	if err != nil {
		return goRoute{}, err
	}
	handlerName, err := routeString(fields[5], "handler")
	if err != nil {
		return goRoute{}, err
	}
	requiredHeader, err := routeString(fields[6], "required_header")
	if err != nil {
		return goRoute{}, err
	}
	pressureBudget, err := routeInt(fields[7], "pressure_budget")
	if err != nil {
		return goRoute{}, err
	}
	handler, err := routeHandler(k, env, name, handlerName)
	if err != nil {
		return goRoute{}, err
	}
	if name == "" || handlerName == "" {
		return goRoute{}, errors.New("kh-route name and handler must not be empty")
	}
	if path == "" || !strings.HasPrefix(path, "/") {
		return goRoute{}, fmt.Errorf("kh-route %s pattern must start with /", name)
	}
	if !validRouteMethod(method) {
		return goRoute{}, fmt.Errorf("kh-route %s method must be GET, POST, PUT, PATCH, DELETE, or ANY", name)
	}
	if pressureBudget < 0 {
		return goRoute{}, fmt.Errorf("kh-route %s pressure_budget must be non-negative", name)
	}
	return goRoute{
		name:           name,
		method:         method,
		path:           path,
		handlerName:    handlerName,
		requiredHeader: requiredHeader,
		pressureBudget: pressureBudget,
		handler:        handler,
		typedRequest:   true,
	}, nil
}

func routeString(v Value, field string) (string, error) {
	if v.Kind != VStr {
		return "", fmt.Errorf("kh-route %s must be a string", field)
	}
	return v.Str, nil
}

func routeInt(v Value, field string) (int64, error) {
	if v.Kind != VInt {
		return 0, fmt.Errorf("kh-route %s must be an integer", field)
	}
	return v.Int, nil
}

func routeHandler(k *Kernel, env *Frame, routeName, handlerName string) (*Closure, error) {
	handlerID := NameID(k.internString(handlerName).Inst)
	v, ok := env.Lookup(handlerID)
	if !ok {
		return nil, fmt.Errorf("kh-route %s handler %s is not bound", routeName, handlerName)
	}
	if v.Kind != VClosure {
		return nil, fmt.Errorf("kh-route %s handler %s must resolve to a closure", routeName, handlerName)
	}
	return v.Cl, nil
}

func validRouteMethod(method string) bool {
	switch method {
	case "GET", "POST", "PUT", "PATCH", "DELETE", "ANY":
		return true
	default:
		return false
	}
}

func (p *goServeProgram) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	worker := p.pool.Get().(*goServeWorker)
	defer p.pool.Put(worker)
	worker.serve(w, r)
}

func (wkr *goServeWorker) serve(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if recovered := recover(); recovered != nil {
			http.Error(w, fmt.Sprintf("native handler panic: %v\n", recovered), http.StatusInternalServerError)
		}
	}()
	route := wkr.match(r)
	if route == nil {
		if wkr.program != nil && wkr.program.upstream != nil {
			wkr.fanout(w, r)
			return
		}
		http.NotFound(w, r)
		return
	}
	requestValue, err := requestValue(route, r)
	if err != nil {
		http.Error(w, fmt.Sprintf("native request read failed: %v\n", err), http.StatusBadRequest)
		return
	}
	call := NewCallFrame(route.handler.Env, len(route.handler.Params))
	if len(route.handler.Params) == 1 {
		call.Bind(route.handler.Params[0], requestValue)
	} else if len(route.handler.Params) != 0 {
		http.Error(w, "native handler must accept zero or one request argument\n", http.StatusInternalServerError)
		return
	}
	result := wkr.k.walk(route.handler.Body, call)
	status, headers, body, ok := formHTTPResponse(result)
	if !ok {
		status = http.StatusOK
		body = formValueString(result)
		headers = http.Header{}
	}
	for key, vals := range headers {
		for _, val := range vals {
			w.Header().Add(key, val)
		}
	}
	setRouteDecisionHeaders(
		w.Header(),
		routeHowNative,
		nativeRouteWhere(route, r),
		routeDecisionWho(r),
		routeDecisionWhen(),
	)
	w.WriteHeader(status)
	_, _ = w.Write([]byte(body))
	wkr.k.substrateGC([]Value{result}, wkr.env)
}

func (wkr *goServeWorker) fanout(w http.ResponseWriter, r *http.Request) {
	target := upstreamURL(wkr.program.upstream, r.URL)
	body, err := io.ReadAll(io.LimitReader(r.Body, 10<<20))
	if err != nil {
		http.Error(w, fmt.Sprintf("fanout request read failed: %v\n", err), http.StatusBadRequest)
		return
	}
	req, err := http.NewRequestWithContext(r.Context(), r.Method, target, bytes.NewReader(body))
	if err != nil {
		http.Error(w, fmt.Sprintf("fanout request build failed: %v\n", err), http.StatusBadGateway)
		return
	}
	copyForwardHeaders(req.Header, r.Header)
	when := routeDecisionWhen()
	who := routeDecisionWho(r)
	where := fanoutRouteWhere(target)
	setRouteDecisionHeaders(req.Header, routeHowFanout, where, who, when)
	setFanoutNativeInvitationHeaders(req.Header)
	req.Header.Set("X-Forwarded-Host", r.Host)
	req.Header.Set("X-Forwarded-Proto", "http")
	resp, err := wkr.program.client.Do(req)
	if err != nil {
		http.Error(w, fmt.Sprintf("fanout upstream failed: %v\n", err), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	copyResponseHeaders(w.Header(), resp.Header)
	setRouteDecisionHeaders(
		w.Header(),
		routeHowFanout,
		where,
		who,
		when,
	)
	setFanoutNativeInvitationHeaders(w.Header())
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, io.LimitReader(resp.Body, 25<<20))
}

func setRouteDecisionHeaders(headers http.Header, how, where, who, when string) {
	headers.Set(headerFormRouter, sanitizeDecisionHeader(how))
	headers.Set(headerRouteHow, sanitizeDecisionHeader(how))
	headers.Set(headerRouteWhere, sanitizeDecisionHeader(where))
	headers.Set(headerRouteWho, sanitizeDecisionHeader(who))
	headers.Set(headerRouteWhen, sanitizeDecisionHeader(when))
}

func setFanoutNativeInvitationHeaders(headers http.Header) {
	headers.Set(headerNativeInvite, nativeInviteValue)
	headers.Set(headerNativeState, nativeInviteState)
	headers.Set(headerNativeProtocol, nativeInviteProtocol)
	headers.Set(headerNativePath, routeHowFanout)
	headers.Set(headerNativeDecline, nativeInviteDecline)
	headers.Set(headerNativeFallback, "X-Form-Python-Fallback")
}

func routeDecisionWhen() string {
	return time.Now().UTC().Format(time.RFC3339Nano)
}

func routeDecisionWho(r *http.Request) string {
	for _, name := range []string{"X-Coherence-Agent", "X-Codex-Agent", "X-Actor", "User-Agent"} {
		if value := r.Header.Get(name); value != "" {
			return value
		}
	}
	if r.RemoteAddr != "" {
		return r.RemoteAddr
	}
	return "unknown"
}

func nativeRouteWhere(route *goRoute, r *http.Request) string {
	return "route:" + route.name + " pattern:" + route.path + " request:" + r.URL.EscapedPath()
}

func fanoutRouteWhere(target string) string {
	parsed, err := url.Parse(target)
	if err != nil {
		return "upstream:unknown"
	}
	parsed.RawQuery = ""
	parsed.Fragment = ""
	return "upstream:" + parsed.String()
}

func sanitizeDecisionHeader(value string) string {
	value = strings.Map(func(r rune) rune {
		if r == '\r' || r == '\n' || r == '\t' {
			return ' '
		}
		if r < 0x20 || r == 0x7f {
			return -1
		}
		return r
	}, value)
	value = strings.Join(strings.Fields(value), " ")
	if value == "" {
		return "unknown"
	}
	if len(value) > maxDecisionHeaderLen {
		return value[:maxDecisionHeaderLen]
	}
	return value
}

func upstreamURL(base *url.URL, requestURL *url.URL) string {
	out := *base
	basePath := strings.TrimRight(base.EscapedPath(), "/")
	reqPath := requestURL.EscapedPath()
	if reqPath == "" {
		reqPath = "/"
	}
	if basePath == "" {
		out.Path = reqPath
	} else {
		out.Path = basePath + "/" + strings.TrimLeft(reqPath, "/")
	}
	out.RawQuery = requestURL.RawQuery
	out.Fragment = ""
	return out.String()
}

func copyForwardHeaders(dst, src http.Header) {
	for key, vals := range src {
		if hopByHopHeader(key) || routerOwnedHeader(key) {
			continue
		}
		for _, val := range vals {
			dst.Add(key, val)
		}
	}
}

func copyResponseHeaders(dst, src http.Header) {
	for key, vals := range src {
		if hopByHopHeader(key) || routerOwnedHeader(key) || strings.EqualFold(key, "Content-Length") {
			continue
		}
		for _, val := range vals {
			dst.Add(key, val)
		}
	}
}

func routerOwnedHeader(key string) bool {
	return strings.EqualFold(key, headerFormRouter) ||
		strings.EqualFold(key, headerRouteHow) ||
		strings.EqualFold(key, headerRouteWhere) ||
		strings.EqualFold(key, headerRouteWhen) ||
		strings.EqualFold(key, headerRouteWho) ||
		strings.EqualFold(key, headerNativeInvite) ||
		strings.EqualFold(key, headerNativeState) ||
		strings.EqualFold(key, headerNativeProtocol) ||
		strings.EqualFold(key, headerNativePath) ||
		strings.EqualFold(key, headerNativeDecline) ||
		strings.EqualFold(key, headerNativeFallback)
}

func hopByHopHeader(key string) bool {
	switch strings.ToLower(key) {
	case "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
		"te", "trailer", "transfer-encoding", "upgrade":
		return true
	default:
		return false
	}
}

func (wkr *goServeWorker) match(r *http.Request) *goRoute {
	for i := range wkr.routes {
		route := &wkr.routes[i]
		if !routeMethodMatches(route.method, r.Method) {
			continue
		}
		if !routePathMatches(route.path, r.URL.Path) {
			continue
		}
		if route.requiredHeader != "" && r.Header.Get(route.requiredHeader) == "" {
			continue
		}
		if route.pressureBudget >= 0 {
			return route
		}
	}
	return nil
}

func routeMethodMatches(routeMethod, requestMethod string) bool {
	return routeMethod == "ANY" || routeMethod == requestMethod
}

func routePathMatches(pattern, path string) bool {
	if strings.HasSuffix(pattern, "*") {
		return routeWildcardPathMatches(pattern, path)
	}
	if strings.Contains(pattern, "{") || strings.Contains(pattern, "/:") {
		return routeTemplatePathMatches(pattern, path)
	}
	return pattern == path
}

func routeWildcardPathMatches(pattern, path string) bool {
	prefix := strings.TrimSuffix(pattern, "*")
	if !strings.HasPrefix(path, prefix) {
		return false
	}
	if strings.HasSuffix(prefix, "/") {
		return true
	}
	remainder := strings.TrimPrefix(path, prefix)
	return remainder != "" && !strings.Contains(remainder, "/")
}

func routeTemplatePathMatches(pattern, path string) bool {
	patternParts := strings.Split(strings.Trim(pattern, "/"), "/")
	pathParts := strings.Split(strings.Trim(path, "/"), "/")
	if len(patternParts) != len(pathParts) {
		return false
	}
	for i, patternPart := range patternParts {
		if routeTemplateSegment(patternPart) {
			if pathParts[i] == "" {
				return false
			}
			continue
		}
		if patternPart != pathParts[i] {
			return false
		}
	}
	return true
}

func routeTemplateSegment(segment string) bool {
	if strings.HasPrefix(segment, ":") && len(segment) > 1 {
		return true
	}
	return strings.HasPrefix(segment, "{") && strings.HasSuffix(segment, "}") && len(segment) > 2
}

func requestValue(route *goRoute, r *http.Request) (Value, error) {
	if route.typedRequest {
		return khRequestValue(r)
	}
	return requestAlistValue(r), nil
}

func khRequestValue(r *http.Request) (Value, error) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 10<<20))
	if err != nil {
		return Value{}, err
	}
	headers := []Value{}
	for key, values := range r.Header {
		for _, value := range values {
			headers = append(headers, Value{Kind: VList, List: []Value{
				{Kind: VInt, Int: khTagHeader},
				{Kind: VStr, Str: key},
				{Kind: VStr, Str: value},
			}})
		}
	}
	query := []Value{}
	for key, values := range r.URL.Query() {
		for _, value := range values {
			query = append(query, Value{Kind: VList, List: []Value{
				{Kind: VInt, Int: khTagField},
				{Kind: VStr, Str: key},
				{Kind: VStr, Str: value},
			}})
		}
	}
	return Value{Kind: VList, List: []Value{
		{Kind: VInt, Int: khTagRequest},
		{Kind: VStr, Str: r.Method},
		{Kind: VStr, Str: r.URL.Path},
		{Kind: VList, List: headers},
		{Kind: VList, List: query},
		{Kind: VStr, Str: string(body)},
	}}, nil
}

func requestAlistValue(r *http.Request) Value {
	pairs := []Value{
		pairValue("__method__", r.Method),
		pairValue("__path__", r.URL.Path),
	}
	for key, values := range r.URL.Query() {
		for _, value := range values {
			pairs = append(pairs, pairValue(key, value))
		}
	}
	return Value{Kind: VList, List: pairs}
}

func pairValue(key, value string) Value {
	return Value{Kind: VList, List: []Value{
		{Kind: VStr, Str: key},
		{Kind: VStr, Str: value},
	}}
}

func formHTTPResponse(v Value) (int, http.Header, string, bool) {
	if v.Kind != VList || len(v.List) != 4 || v.List[0].Kind != VInt || v.List[0].Int != khTagResponse {
		return 0, nil, "", false
	}
	status := int(v.List[1].Int)
	headers := http.Header{}
	if v.List[2].Kind == VList {
		for _, raw := range v.List[2].List {
			if raw.Kind != VList || len(raw.List) != 3 {
				continue
			}
			if raw.List[0].Kind == VInt && raw.List[0].Int == khTagHeader &&
				raw.List[1].Kind == VStr && raw.List[2].Kind == VStr {
				headers.Add(raw.List[1].Str, raw.List[2].Str)
			}
		}
	}
	body := formValueString(v.List[3])
	return status, headers, body, true
}

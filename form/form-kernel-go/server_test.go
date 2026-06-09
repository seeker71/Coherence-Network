package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestUpstreamURLPreservesPathAndQuery(t *testing.T) {
	base, err := url.Parse("https://api.example.test/root/")
	if err != nil {
		t.Fatal(err)
	}
	reqURL, err := url.Parse("/api/substrate/form?mode=ast&x=1")
	if err != nil {
		t.Fatal(err)
	}
	got := upstreamURL(base, reqURL)
	want := "https://api.example.test/root/api/substrate/form?mode=ast&x=1"
	if got != want {
		t.Fatalf("upstreamURL() = %q, want %q", got, want)
	}
}

func TestFanoutForwardsBodyAndMarksBridge(t *testing.T) {
	var sawPath string
	var sawBody string
	var sawRouter string
	var sawHow string
	var sawWhere string
	var sawWho string
	var sawWhen string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sawPath = r.URL.RequestURI()
		sawRouter = r.Header.Get("X-Form-Router")
		sawHow = r.Header.Get("X-Form-Route-How")
		sawWhere = r.Header.Get("X-Form-Route-Where")
		sawWho = r.Header.Get("X-Form-Route-Who")
		sawWhen = r.Header.Get("X-Form-Route-When")
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatal(err)
		}
		sawBody = string(body)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		_, _ = w.Write([]byte(`{"kind":"bridge"}`))
	}))
	defer upstream.Close()

	base, err := url.Parse(upstream.URL)
	if err != nil {
		t.Fatal(err)
	}
	worker := &goServeWorker{
		program: &goServeProgram{
			upstream: base,
			client: &http.Client{
				Timeout: 5 * time.Second,
			},
		},
	}

	req := httptest.NewRequest(
		http.MethodPost,
		"http://native.example.test/api/substrate/form?source=web",
		strings.NewReader(`{"expression":"?lattice","mode":"ast"}`),
	)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Coherence-Agent", "agent with space")
	rec := httptest.NewRecorder()

	worker.fanout(rec, req)
	res := rec.Result()
	defer res.Body.Close()
	gotBody, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}

	if res.StatusCode != http.StatusAccepted {
		t.Fatalf("fanout status = %d, want %d", res.StatusCode, http.StatusAccepted)
	}
	if got := res.Header.Get("X-Form-Router"); got != "fanout-python" {
		t.Fatalf("response X-Form-Router = %q, want fanout-python", got)
	}
	if got := res.Header.Get("X-Form-Route-How"); got != "fanout-python" {
		t.Fatalf("response X-Form-Route-How = %q, want fanout-python", got)
	}
	if got := res.Header.Get("X-Form-Route-Who"); got != "agent with space" {
		t.Fatalf("response X-Form-Route-Who = %q, want sanitized agent", got)
	}
	if got := res.Header.Get("X-Form-Route-Where"); !strings.HasPrefix(got, "upstream:http://") || !strings.HasSuffix(got, "/api/substrate/form") {
		t.Fatalf("response X-Form-Route-Where = %q", got)
	}
	if _, err := time.Parse(time.RFC3339Nano, res.Header.Get("X-Form-Route-When")); err != nil {
		t.Fatalf("response X-Form-Route-When is not RFC3339Nano: %v", err)
	}
	if sawRouter != "fanout-python" {
		t.Fatalf("upstream X-Form-Router = %q, want fanout-python", sawRouter)
	}
	if sawHow != "fanout-python" {
		t.Fatalf("upstream X-Form-Route-How = %q, want fanout-python", sawHow)
	}
	if sawWho != "agent with space" {
		t.Fatalf("upstream X-Form-Route-Who = %q, want sanitized agent", sawWho)
	}
	if !strings.HasPrefix(sawWhere, "upstream:http://") || !strings.HasSuffix(sawWhere, "/api/substrate/form") {
		t.Fatalf("upstream X-Form-Route-Where = %q", sawWhere)
	}
	if _, err := time.Parse(time.RFC3339Nano, sawWhen); err != nil {
		t.Fatalf("upstream X-Form-Route-When is not RFC3339Nano: %v", err)
	}
	if sawPath != "/api/substrate/form?source=web" {
		t.Fatalf("upstream path = %q", sawPath)
	}
	if sawBody != `{"expression":"?lattice","mode":"ast"}` {
		t.Fatalf("upstream body = %q", sawBody)
	}
	if string(gotBody) != `{"kind":"bridge"}` {
		t.Fatalf("response body = %q", string(gotBody))
	}
}

func TestRouteDecisionHeadersShowWhereWhenWhoHow(t *testing.T) {
	headers := http.Header{}
	setRouteDecisionHeaders(
		headers,
		"native-kernel-go",
		"route:health\npattern:/api/health",
		"codex\tagent",
		"2026-06-05T14:29:38Z",
	)

	if got := headers.Get("X-Form-Router"); got != "native-kernel-go" {
		t.Fatalf("X-Form-Router = %q", got)
	}
	if got := headers.Get("X-Form-Route-How"); got != "native-kernel-go" {
		t.Fatalf("X-Form-Route-How = %q", got)
	}
	if got := headers.Get("X-Form-Route-Where"); got != "route:health pattern:/api/health" {
		t.Fatalf("X-Form-Route-Where = %q", got)
	}
	if got := headers.Get("X-Form-Route-Who"); got != "codex agent" {
		t.Fatalf("X-Form-Route-Who = %q", got)
	}
	if got := headers.Get("X-Form-Route-When"); got != "2026-06-05T14:29:38Z" {
		t.Fatalf("X-Form-Route-When = %q", got)
	}
}

func TestHealthRouteNativeOperationalShape(t *testing.T) {
	body, err := os.ReadFile("../../deploy/front-door/api.bml")
	if err != nil {
		t.Fatal(err)
	}
	artifact, err := sourceCompileServeProgram(
		[]sourcePart{{label: "deploy/front-door/api.bml", source: string(body)}},
		"../form-stdlib",
	)
	if err != nil {
		t.Fatalf("sourceCompileServeProgram: %v", err)
	}
	worker, err := buildGoServeWorker(&goServeProgram{artifact: artifact})
	if err != nil {
		t.Fatalf("buildGoServeWorker: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "http://native.example.test/api/health", nil)
	req.Header.Set("Accept", "application/json")
	rec := httptest.NewRecorder()
	worker.serve(rec, req)
	res := rec.Result()
	defer res.Body.Close()
	gotBody, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode != http.StatusOK {
		t.Fatalf("health route status = %d body=%s", res.StatusCode, string(gotBody))
	}
	if got := res.Header.Get("X-Form-Router"); got != "native-kernel-go" {
		t.Fatalf("health route router = %q, want native-kernel-go", got)
	}
	for _, want := range []string{
		`"status":"ok"`,
		`"schema_ok":`,
		`"smart_reap_available":true`,
		`"recent_outcomes":`,
		`"kernel_runtime":"form-kernel-go"`,
	} {
		if !strings.Contains(string(gotBody), want) {
			t.Fatalf("health route body missing %s: %s", want, string(gotBody))
		}
	}
}

func TestCompileSourceSectionNativeReturnsRecipe(t *testing.T) {
	k := NewKernel()
	expr := `(compile_source_section "form.bml" "add(20, 22);" "test/runtime.bml")`
	value := k.walk(readRootFromSource(k, expr), NewFrame(nil))
	if value.Kind != VNodeID {
		t.Fatalf("compile_source_section kind = %v, want VNodeID; err=%q", value.Kind, k.sourceCompileErr)
	}
	if _, ok := k.sourceAttr[value.Nid]; !ok {
		t.Fatalf("compiled recipe %s has no source attribution", value.String())
	}
	got := k.walk(value.Nid, NewFrame(nil))
	if got.Kind != VInt || got.Int != 42 {
		t.Fatalf("compiled recipe walked to %v, want int 42", got)
	}
}

func TestCompileSourceSectionNativeReportsMalformedBMLDef(t *testing.T) {
	k := NewKernel()
	expr := `(do
	  (compile_source_section "form.bml" "def broken(
	    x
	  ) = x;" "test/bad.bml")
	  (source_compile_last_error))`
	got := k.walk(readRootFromSource(k, expr), NewFrame(nil))
	if got.Kind != VStr {
		t.Fatalf("source_compile_last_error kind = %v, want VStr", got.Kind)
	}
	if !strings.Contains(got.Str, "form.bml def missing closing ')' on the definition line: def broken(") {
		t.Fatalf("source_compile_last_error = %q", got.Str)
	}
}

func TestCompileSourceTextNativeReturnsRecipe(t *testing.T) {
	k := NewKernel()
	source := "section [form.bml] {\n add(10, 5);\n}\n"
	expr := "(compile_source_text " + sexpStringLiteral(source) + ` "test/source.bml")`
	value := k.walk(readRootFromSource(k, expr), NewFrame(nil))
	if value.Kind != VNodeID {
		t.Fatalf("compile_source_text kind = %v, want VNodeID; err=%q", value.Kind, k.sourceCompileErr)
	}
	got := k.walk(value.Nid, NewFrame(nil))
	if got.Kind != VInt || got.Int != 15 {
		t.Fatalf("compiled source walked to %v, want int 15", got)
	}
}

func TestSubstrateFormCompilerRouteRunsBML(t *testing.T) {
	body, err := os.ReadFile("../../deploy/front-door/api.bml")
	if err != nil {
		t.Fatal(err)
	}
	artifact, err := sourceCompileServeProgram(
		[]sourcePart{{label: "deploy/front-door/api.bml", source: string(body)}},
		"../form-stdlib",
	)
	if err != nil {
		t.Fatalf("sourceCompileServeProgram: %v", err)
	}
	worker, err := buildGoServeWorker(&goServeProgram{artifact: artifact})
	if err != nil {
		t.Fatalf("buildGoServeWorker: %v", err)
	}

	req := httptest.NewRequest(
		http.MethodPost,
		"http://native.example.test/api/substrate/form",
		strings.NewReader(`{"expression":"add(20, 22);","mode":"run","grammar":"form.bml"}`),
	)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	noHeader := httptest.NewRecorder()
	worker.serve(noHeader, req)
	noHeaderRes := noHeader.Result()
	defer noHeaderRes.Body.Close()
	noHeaderBody, err := io.ReadAll(noHeaderRes.Body)
	if err != nil {
		t.Fatal(err)
	}
	if noHeaderRes.StatusCode != http.StatusOK {
		t.Fatalf("ordinary substrate form status = %d body=%s", noHeaderRes.StatusCode, string(noHeaderBody))
	}
	if got := noHeaderRes.Header.Get("X-Form-Router"); got != "native-kernel-go" {
		t.Fatalf("ordinary substrate form router = %q, want native-kernel-go", got)
	}
	for _, want := range []string{`"kind":"value"`, `"value_kind":"int"`, `"value":42`, `"handler":"api_substrate_form"`} {
		if !strings.Contains(string(noHeaderBody), want) {
			t.Fatalf("ordinary substrate form body missing %s: %s", want, string(noHeaderBody))
		}
	}

	req = httptest.NewRequest(
		http.MethodPost,
		"http://native.example.test/api/substrate/form",
		strings.NewReader(`{"expression":"add(20, 22);","mode":"run","grammar":"form.bml"}`),
	)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("X-Form-Compiler", "form.bml")
	rec := httptest.NewRecorder()
	worker.serve(rec, req)
	res := rec.Result()
	defer res.Body.Close()
	gotBody, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode != http.StatusOK {
		t.Fatalf("compiler route status = %d body=%s", res.StatusCode, string(gotBody))
	}
	if got := res.Header.Get("X-Form-Router"); got != "native-kernel-go" {
		t.Fatalf("compiler route router = %q, want native-kernel-go", got)
	}
	for _, want := range []string{`"kind":"value"`, `"value_kind":"int"`, `"value":42`, `"handler":"api_substrate_form"`} {
		if !strings.Contains(string(gotBody), want) {
			t.Fatalf("compiler route body missing %s: %s", want, string(gotBody))
		}
	}
}

func TestRuntimeEventsCreateRouteValidatesNatively(t *testing.T) {
	body, err := os.ReadFile("../../deploy/front-door/api.bml")
	if err != nil {
		t.Fatal(err)
	}
	artifact, err := sourceCompileServeProgram(
		[]sourcePart{{label: "deploy/front-door/api.bml", source: string(body)}},
		"../form-stdlib",
	)
	if err != nil {
		t.Fatalf("sourceCompileServeProgram: %v", err)
	}
	worker, err := buildGoServeWorker(&goServeProgram{artifact: artifact})
	if err != nil {
		t.Fatalf("buildGoServeWorker: %v", err)
	}

	req := httptest.NewRequest(
		http.MethodPost,
		"http://native.example.test/api/runtime/events",
		strings.NewReader(`{"source":"outside","endpoint":"/api/health?x=1","method":"GET","status_code":200,"runtime_ms":12.5,"metadata":{"probe":true}}`),
	)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	rec := httptest.NewRecorder()
	worker.serve(rec, req)
	res := rec.Result()
	defer res.Body.Close()
	gotBody, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("runtime event validation status = %d body=%s", res.StatusCode, string(gotBody))
	}
	if got := res.Header.Get("X-Form-Router"); got != "native-kernel-go" {
		t.Fatalf("runtime event validation router = %q, want native-kernel-go", got)
	}
	if want := "source must be api, web, web_api, or worker"; !strings.Contains(string(gotBody), want) {
		t.Fatalf("runtime event validation body missing %q: %s", want, string(gotBody))
	}
}

func TestViewsPingRouteValidatesNatively(t *testing.T) {
	body, err := os.ReadFile("../../deploy/front-door/api.bml")
	if err != nil {
		t.Fatal(err)
	}
	artifact, err := sourceCompileServeProgram(
		[]sourcePart{{label: "deploy/front-door/api.bml", source: string(body)}},
		"../form-stdlib",
	)
	if err != nil {
		t.Fatalf("sourceCompileServeProgram: %v", err)
	}
	worker, err := buildGoServeWorker(&goServeProgram{artifact: artifact})
	if err != nil {
		t.Fatalf("buildGoServeWorker: %v", err)
	}

	req := httptest.NewRequest(
		http.MethodPost,
		"http://native.example.test/api/views/ping",
		strings.NewReader(`{"source_page":"/native-route-probe"}`),
	)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	rec := httptest.NewRecorder()
	worker.serve(rec, req)
	res := rec.Result()
	defer res.Body.Close()
	gotBody, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("views ping validation status = %d body=%s", res.StatusCode, string(gotBody))
	}
	if got := res.Header.Get("X-Form-Router"); got != "native-kernel-go" {
		t.Fatalf("views ping validation router = %q, want native-kernel-go", got)
	}
	if want := "asset_id is required"; !strings.Contains(string(gotBody), want) {
		t.Fatalf("views ping validation body missing %q: %s", want, string(gotBody))
	}
}

func TestGatesMainHeadRouteFetchesExternalHTTPInBML(t *testing.T) {
	const sha = "386fed3dce5f949e7d0f61ac55f3506115171cc0"
	var sawPath string
	var sawAccept string
	var sawAPIVersion string
	var sawUserAgent string
	var sawAuthorization string
	github := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sawPath = r.URL.Path
		sawAccept = r.Header.Get("Accept")
		sawAPIVersion = r.Header.Get("X-GitHub-Api-Version")
		sawUserAgent = r.Header.Get("User-Agent")
		sawAuthorization = r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"commit":{"sha":"` + sha + `"}}`))
	}))
	defer github.Close()

	configPath := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(
		configPath,
		[]byte(`{"github":{"api_base":"`+github.URL+`","token":"test-token"},"release_gates":{"branch_head_sha_timeout_seconds":2.0,"branch_head_sha_cache_ttl_seconds":45.0}}`),
		0o600,
	); err != nil {
		t.Fatal(err)
	}
	oldConfigPath := goKernelConfigPath
	goKernelConfigPath = configPath
	t.Cleanup(func() {
		goKernelConfigPath = oldConfigPath
		goVolatileCells.delete("github.branch_head_sha", "seeker71/Coherence-Network|main")
	})

	body, err := os.ReadFile("../../deploy/front-door/api.bml")
	if err != nil {
		t.Fatal(err)
	}
	artifact, err := sourceCompileServeProgram(
		[]sourcePart{{label: "deploy/front-door/api.bml", source: string(body)}},
		"../form-stdlib",
	)
	if err != nil {
		t.Fatalf("sourceCompileServeProgram: %v", err)
	}
	worker, err := buildGoServeWorker(&goServeProgram{artifact: artifact})
	if err != nil {
		t.Fatalf("buildGoServeWorker: %v", err)
	}

	req := httptest.NewRequest(
		http.MethodGet,
		"http://native.example.test/api/gates/main-head?repo=seeker71/Coherence-Network&branch=main&timeout_seconds=2.0",
		nil,
	)
	req.Header.Set("Accept", "application/json")
	rec := httptest.NewRecorder()
	worker.serve(rec, req)
	res := rec.Result()
	defer res.Body.Close()
	gotBody, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}

	if res.StatusCode != http.StatusOK {
		t.Fatalf("gates main-head status = %d body=%s", res.StatusCode, string(gotBody))
	}
	if got := res.Header.Get("X-Form-Router"); got != "native-kernel-go" {
		t.Fatalf("gates main-head router = %q, want native-kernel-go", got)
	}
	if sawPath != "/repos/seeker71/Coherence-Network/branches/main" {
		t.Fatalf("github path = %q", sawPath)
	}
	if sawAccept != "application/vnd.github+json" {
		t.Fatalf("github Accept = %q", sawAccept)
	}
	if sawAPIVersion != "2022-11-28" {
		t.Fatalf("github X-GitHub-Api-Version = %q", sawAPIVersion)
	}
	if sawUserAgent != "CoherenceNetworkNativeKernel/1.0" {
		t.Fatalf("github User-Agent = %q", sawUserAgent)
	}
	if sawAuthorization != "Bearer test-token" {
		t.Fatalf("github Authorization = %q", sawAuthorization)
	}
	for _, want := range []string{`"repo":"seeker71/Coherence-Network"`, `"branch":"main"`, `"sha":"` + sha + `"`} {
		if !strings.Contains(string(gotBody), want) {
			t.Fatalf("gates main-head body missing %s: %s", want, string(gotBody))
		}
	}
}

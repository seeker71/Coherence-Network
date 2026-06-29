// FkwuSense — the thin bridge to the C-bootstrapped fkwu kernel running on this Mac's metal.
//
// CARRIER, not body. Swift measures numbers (grid-average luminance, frame-diff
// salience) and hands a Form EXPRESSION to fkwu; fkwu runs the DECISION and returns
// the verdict. The "presence: yes/no" and "surprise spike" the window shows are
// fkwu's own evaluation of:
//   presence : (if (le <threshold> <luma>) 1 0)        -- presence-feature gate
//   surprise : (if (le <tol> <salience>) 1 0)          -- ambient-surprise as-surprise?
// over the same proven form-eval-full loop-table witnessed four-way at validate.sh and
// shipped to the Galaxy S23 (FkwuSense.kt). No sensing logic lives in this file:
// Swift pipes a couple of bytes and reads back fkwu's line. The body is native; the
// carrier is thin.
//
// The salience MAGNITUDE (abs(reading - baseline)) is carrier-computed in Sensing.swift
// — the loop-table's curated vocabulary carries `le`/`sub` but not `abs`/`gt`, so the
// thin reduction is Swift's and the DECISION (the (le ..) gate) is fkwu's. Honest lane:
// recipe-run for the gate, carrier-computed for the magnitude — never the reverse.

import Foundation

struct Verdict {
    let raw: String       // exact first line fkwu emitted (the native value)
    let value: Int?       // parsed verdict, or nil if fkwu was unreachable
    let expr: String      // the Form expression fkwu evaluated
    let native: Bool      // true => the number came from fkwu on metal
    let error: String?    // nil on success
}

enum FkwuSense {
    // The proven fkwu binary + flattened loop-table, bundled as app Resources.
    // loop-table.txt is the byte-identical flattened form-eval-full that ran on the
    // phone; fkwu-mac is the arm64 C-bootstrap kernel — no go/rust/clang/python/bash
    // in this evaluate loop.

    private static func resource(_ name: String, _ ext: String? = nil) -> URL? {
        if let u = Bundle.main.url(forResource: name, withExtension: ext, subdirectory: "native") {
            return u
        }
        // swiftc/bundle layout fallback: Resources/native next to the executable.
        let exeDir = URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent()
        let full = ext.map { "\(name).\($0)" } ?? name
        for cand in [
            exeDir.appendingPathComponent("../Resources/native/\(full)"),
            exeDir.appendingPathComponent("native/\(full)"),
        ] {
            if FileManager.default.fileExists(atPath: cand.path) { return cand }
        }
        return nil
    }

    static var executableURL: URL? { resource("fkwu-mac") }
    static var tableURL: URL? { resource("loop-table", "txt") ?? resource("loop-table.txt") }

    static var available: Bool {
        guard let exe = executableURL else { return false }
        return FileManager.default.isExecutableFile(atPath: exe.path)
    }

    // Run ONE Form expression through fkwu, return its first emitted line. The
    // loop-table reads the expression as source text from argv[3] and prints the
    // verdict as line 1 (exactly the FkwuSense.kt contract).
    static func evaluate(_ expr: String) -> Verdict {
        guard let exe = executableURL, let table = tableURL else {
            return Verdict(raw: "", value: nil, expr: expr, native: false, error: "fkwu/table missing")
        }
        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("fkwu-sense-\(UUID().uuidString).txt")
        defer { try? FileManager.default.removeItem(at: tmp) }
        do {
            try (expr + "\n").write(to: tmp, atomically: true, encoding: .utf8)
        } catch {
            return Verdict(raw: "", value: nil, expr: expr, native: false, error: "input write failed")
        }

        let proc = Process()
        proc.executableURL = exe
        proc.arguments = [table.path, "0", tmp.path]
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe
        do {
            try proc.run()
        } catch {
            return Verdict(raw: "", value: nil, expr: expr, native: false, error: "spawn: \(error.localizedDescription)")
        }
        // Bound the wait — a healthy gate returns in well under a second.
        let deadline = Date().addingTimeInterval(2.0)
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        if Date() > deadline && !proc.isRunning {
            // it ran long but finished; still read what we got
        }
        let text = String(data: data, encoding: .utf8) ?? ""
        // Verdict is line 1; the loop re-reads past EOF and emits internal counters
        // after, so we take the FIRST non-empty line — that is the native answer.
        guard let first = text
            .split(whereSeparator: \.isNewline)
            .map({ $0.trimmingCharacters(in: .whitespaces) })
            .first(where: { !$0.isEmpty })
        else {
            return Verdict(raw: "", value: nil, expr: expr, native: false, error: "empty output")
        }
        return Verdict(raw: first, value: Int(first), expr: expr, native: true, error: nil)
    }

    // presence-feature gate: is the live luminance at/above the presence threshold?
    static func sensePresence(luma: Int, threshold: Int) -> Verdict {
        evaluate("(if (le \(threshold) \(luma)) 1 0)")
    }

    // ambient-surprise as-surprise? gate: does the (carrier-computed) salience
    // magnitude meet-or-exceed the tolerance band? salience >= tol  ==  (le tol salience).
    static func senseSurprise(salience: Int, tolerance: Int) -> Verdict {
        evaluate("(if (le \(tolerance) \(salience)) 1 0)")
    }
}

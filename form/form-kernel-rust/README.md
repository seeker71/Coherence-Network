# form-kernel-rust

Vertical-slice Rust host for Form-on-top. Executes Form recipe trees and binary artifacts. Carries the substrate (content-addressed intern), the walker (22 RBasic arms), frames + closures, native primitives (strings, lists, file I/O), and the Form binary artifact loader.

```bash
cargo run --release --quiet -- ../form-samples/fact.fk          # → 3628800
cargo run --release --quiet -- --expr "(add 2 (mul 3 4))"       # → 14
cargo run --release --quiet -- --bench                          # benchmark suite
```

## `serve` — kernel-as-HTTP-listener (proof-of-shape)

```bash
cargo build --release
./target/release/form-kernel-rust serve --port 8001 --routes examples/routes.fk
# in another shell:
curl http://127.0.0.1:8001/hello            # → Hello from the kernel
curl 'http://127.0.0.1:8001/echo?msg=foo'   # → foo
python3 test_serve.py                       # full pass: /hello, /echo, /missing → 404
```

A 50-line raw `std::net::TcpListener` listens on a port, parses the request line into Form values (method, path, query alist), looks up a handler closure from `routes.fk`'s top-level `routes` binding, walks the closure, and writes the returned value back as the response body. No hyper, no actix, no async runtime — the kernel's existing socket primitives' siblings.

This is **gesture not replacement** for Breath 8 of [`../kernel-roadmap.md`](../kernel-roadmap.md). The body's primary HTTP doorway stays FastAPI; this exists so the body can feel "kernel CAN listen" before betting more of the stack on it. No middleware, no pydantic, no OpenAPI, no auth — those live behind the FastAPI surface that is still the right tool for that job.

Sibling: [`../form-kernel-go/`](../form-kernel-go/). Comparison + runtime numbers: [`../kernel-comparison.md`](../kernel-comparison.md).

Source upstream:
- Floor scope named in [`docs/coherence-substrate/form-runtime-in-form.form`](../../docs/coherence-substrate/form-runtime-in-form.form).
- Category numbering aligned with [`api/app/services/substrate/category.py`](../../api/app/services/substrate/category.py).
- Sample `.fk` source files in [`../form-samples/`](../form-samples/).

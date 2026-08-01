# Security policy

## Supported versions

The latest version released on PyPI. Fixes are made against the current release
rather than backported to older ones.

## Reporting a vulnerability

Please report privately through GitHub **Security Advisories** on this repository:
open the Security tab, then "Report a vulnerability". That path keeps a report
private between you and the maintainer until a fix is ready, which a public issue
cannot do.

If Security Advisories are not available to you for any reason, open an issue with
the minimum detail needed to confirm a person will see it and no exploit detail in
the issue body, and mention **@Ab-Romia** directly so it is not missed; the
conversation will move to a private channel from there.

Please do not open a public issue that describes a vulnerability in detail.

What to expect: an acknowledgement within three working days, an assessment within
ten, and credit in the eventual advisory unless you would rather stay unnamed.

## In scope

- Anything that would cause an API key to be written to disk, printed, or included in
  an output file. Keys are read from the environment only, and nothing in this
  package is meant to echo one back.
- The local test page served by `commentdraft ui`. It reads out the whole knowledge
  document through `/prompt` and `/trace` and spends the configured key through
  `/api/reply`, so reaching it at all is the whole of the access it grants. Three
  things stop that, and they are independent on purpose. It binds to `127.0.0.1` and
  there is no flag to bind it anywhere else: `serve` refuses a non-loopback address
  rather than warning about one. Every request is refused unless the connecting peer
  is itself a loopback address, which holds whatever the server was bound to and does
  not depend on any header a client chooses to send. And it checks the request's
  `Host` header against `127.0.0.1`, `localhost` and `::1` to rule out DNS rebinding,
  and rejects any request whose `Origin` header does not match this same page, which
  is what stops a page you happen to have open in another tab from driving it without
  your knowledge. A way around any of that is a vulnerability worth reporting.
- Path traversal through a configured path, a knowledge source handler, or a field in
  a comments CSV.
- Anything that causes the package to make a network request to a host other than the
  configured `[model].base_url`.
- Any way to make this package publish, post, or otherwise transmit a drafted reply
  anywhere on its own. It is not supposed to be able to do this at all, and a way to
  make it happen is the most serious kind of report this project can receive.

## Out of scope

- A model producing a wrong, biased, or otherwise unpleasant draft. Every draft sits
  behind a person reviewing it before it goes anywhere, and that review is the control
  this design relies on rather than treating this as a security bug. See
  `docs/limits.md` and `docs/platform-policy.md`.
- Prompt injection that changes what a **draft** says. A comment can contain
  instructions and a model may follow them; the reviewer reading every row before
  approval is what catches it. Prompt injection that changes what the **program**
  does instead, such as causing an unexpected file write or an unconfigured network
  call, is very much in scope.
- Cost overruns caused by a misconfigured or mispriced model entry.
- Vulnerabilities in a model provider or in the gateway between you and it. Please
  report those directly to whoever operates them.

# Facebook Pages

Reading the comments on posts your Page published, and publishing one approved reply
at a time.

Graph API `v26.0`, released 2026-07-29
(<https://developers.facebook.com/docs/graph-api/changelog>). Every Meta page cited
below was read on **2026-08-01**. Meta stamps most of its documentation with its own
`Updated:` date, and where that date matters it is given next to the link.

## What this gets you, and what it costs

An operator who owns the Page and creates their own Meta app needs **no App Review and
no Business Verification**. Nothing is queued and nobody at Meta reads anything. The
entire access path is you clicking through your own app dashboard and copying two
tokens.

Our estimate is under an hour from a standing start to comments landing in a CSV. That
is our estimate and not a published SLA; Meta publishes none, because there is nothing
to wait for. Of the platforms researched for commentdraft this is the shortest route to
a working connection, which is also our comparison rather than anyone's published claim.

What it costs is on the other side of that.

| Cost | Where it lands |
|---|---|
| The Page token is tied to one human's role on one Page | The person who granted it losing their Page role kills the token, and a new one dies the same way |
| Permissions expire after 90 days of non-use | commentdraft is used in bursts, so this is the failure most operators will meet |
| The rate budget scales with how busy the Page is | A quiet Page has almost no budget. See [Limits](#limits) |
| One endpoint is contested in Meta's own documentation | See [The reply path](#the-reply-path). It is the reason this connector reads back every write |

Distributing commentdraft as a product other people log into is a different story
entirely: that needs Advanced Access, which needs App Review on each permission and
Business Verification.

> "Business Verification is required to get Advanced Access."
>
> <https://developers.facebook.com/docs/graph-api/overview/access-levels>

Everything below is the single-operator path.

## What is verified here, and what is not

**Nobody has run this connector against a real Facebook Page.** It was built and tested
against a fake transport, offline, with no credential in the process. Not one sentence
on this page reports observed behaviour of the live Graph API, and any page that told
you otherwise about a connector in this state would be guessing.

Verified against Meta's live documentation, read 2026-08-01:

| What | How far the check went |
|---|---|
| Endpoint paths and HTTP methods | Read on the reference page for each edge, with the version-specific page cross-checked |
| Scope strings | Read on <https://developers.facebook.com/docs/permissions>, character for character |
| Error codes and subcodes | Read on Meta's error tables, with Meta's own wording kept |
| The access sequence | Read on the access-levels, App Review and Business Verification pages |
| Quoted policy text | Quoted verbatim from the page named beside it, with the date read |
| Meta's own defects | Reproduced through two independent extraction methods before being called defects |

Not verified against a live account, and this list is complete:

- That `POST /v26.0/{comment-id}/comments` creates a reply. Nobody has made the call.
- That `POST /v26.0/{comment_id}` with a `message` edits the comment rather than
  replying to it. Meta documents both readings. See [The reply path](#the-reply-path).
- Which spelling of a comment id (`98765` or `1122334455_98765`) each endpoint hands
  back. The connector treats both as the same comment because it has to.
- Whether the read-back `GET` returns a `parent` object on a freshly created reply.
  The whole write check depends on it.
- What a real Graph error body carries for each subcode, as opposed to what the error
  tables say it carries.
- Whether exchanging a long-lived user token really yields long-lived Page tokens.
- Whether filtering timestamps on our side matches Meta's own ordering on the comments
  edge.

Anything that could not be established at all is under
[What is still unknown](#what-is-still-unknown) rather than smoothed into the prose
above it.

## Before you start

| You need | You do not need |
|---|---|
| A Facebook **Page**. Not a personal profile: every endpoint here is Page-scoped | A Business Manager account |
| A Facebook account holding a role on that Page | A verified business |
| A Meta developer account, registered with an authentic account (Developer Policy 1.1) | A linked or verified domain |
| An app you create yourself, of the **Business** type | A public HTTPS endpoint |
| Python 3 and commentdraft installed | Any hosting at all |

### Which Page roles work

Meta splits Page access into tasks. The definitions are verbatim from
<https://developers.facebook.com/docs/pages-api/overview/>:

| Task | What Meta says it does | Needed here |
|---|---|---|
| `MODERATE` | "Respond to comments on Page posts as the Page" and "Delete comments on Page posts" | Yes, for both reading and publishing |
| `CREATE_CONTENT` | "Publish content as the Page on the Page" | Yes, in practice: the read edges name it as an alternative to `MODERATE` |
| `MANAGE` | "Assign and manage Page tasks" | No |
| `MESSAGING` | "Send messages as the Page" | No |
| `ANALYZE` | View "Insights of the Page" | No |
| `ADVERTISE` | "Create ads", "Create unpublished Page Posts" | No |

`MODERATE` is the one that matters, and it is defined as the thing this connector does.
A full Page admin holds every task; a partial-access user may hold none of the ones you
need. Meta states the floor separately:

> "All users requesting access to a Page using permissions must be able to perform the
> `MODERATE` task on the Page being queried."
>
> <https://developers.facebook.com/docs/graph-api/reference/v26.0/page>

If your Page is on the New Pages Experience, only a Page access token reaches the API at
all (<https://developers.facebook.com/docs/pages-api/>).

## Getting a token

commentdraft ships no login helper. You perform this exchange yourself, once, and put
the result in an environment variable.

1. Sign in at <https://developers.facebook.com/> and register as a developer. Developer
   Policy 1.1: "Develop and manage your App with an authentic account."
   (<https://developers.facebook.com/devpolicy/>)

2. Create a new app in the App Dashboard and choose the **Business** app type. The type
   is what keeps you out of App Review:

   > "Business, Consumer, and Gaming apps are automatically approved for Standard Access
   > for all permissions and features available to their app type."
   >
   > <https://developers.facebook.com/docs/graph-api/overview/access-levels>

3. Add the **Facebook Login** product. Set an OAuth redirect URI. For a command line
   tool a loopback listener is the usual shape: `http://localhost:8377/callback`.

4. Leave the app in **Development mode** and confirm you hold the Administrator role on
   it, which you do as its creator. Both facts are load bearing:

   > "Permissions with Standard Access can only be requested from app users who have a
   > role on the requesting app."
   >
   > <https://developers.facebook.com/docs/graph-api/overview/access-levels>

   > "If your app will only be used by app users who have a role on the app itself, App
   > Review is not required."
   >
   > <https://developers.facebook.com/docs/app-review/introduction>

5. Run the Facebook Login flow requesting exactly these scopes. Copy them character for
   character:

   ```
   pages_show_list
   pages_read_engagement
   pages_read_user_content
   pages_manage_engagement
   ```

   `pages_manage_engagement` is needed only if you will publish. Leave it out to start.
   Add `pages_manage_metadata` only if you are subscribing to webhooks, which
   commentdraft does not do.

   Do **not** request `pages_read_user_engagement`. Meta's own Pages API guide lists it
   (<https://developers.facebook.com/docs/pages-api/comments-mentions/>, Updated
   2026-04-16) and no such permission exists. It is absent from the permissions
   reference and from the full permissions list. Read it as a typo for
   `pages_read_user_content`, which is the one you actually need:

   > "The **pages_read_user_content** permission allows your app to read user generated
   > content on the Page, such as posts, comments, and ratings by users or other Pages,
   > and to delete user comments on Page posts."
   >
   > <https://developers.facebook.com/docs/permissions/reference/pages_read_user_content>

   `pages_read_engagement` is not a substitute. It covers content posted **by** the
   Page. A comment left by a member of the public is user-generated content, and reading
   it is what `pages_read_user_content` grants. Requesting only the former gets you a
   tool that can see your own posts and nothing anyone said under them. Both are listed
   as required on the Page feed edge
   (<https://developers.facebook.com/docs/graph-api/reference/v26.0/page/feed>).

   The login flow returns a short-lived user access token.

6. Exchange it for a long-lived user access token:

   ```
   GET https://graph.facebook.com/v26.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app-id}
     &client_secret={app-secret}
     &fb_exchange_token={short-lived-user-token}
   ```

   <https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived>

7. Exchange that for Page access tokens:

   ```
   GET https://graph.facebook.com/v26.0/{user-id}/accounts
     ?access_token={long-lived-user-token}
   ```

   The response is "an array of objects. Each object contains information about a
   specific Page including the name, ID, a short-lived Page access token, tasks you can
   perform on the Page, and more."
   (<https://developers.facebook.com/docs/pages-api/getting-started/>)

   A long-lived user token in yields long-lived Page tokens out. Meta on what
   long-lived means for each:

   > "A long-lived token generally lasts about 60 days." (user token)
   >
   > "Long-lived Page access token do not have an expiration date and only expire or are
   > invalidated under certain conditions." (Page token)
   >
   > <https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived>

   Those conditions are in [What breaks](#what-breaks-and-what-each-failure-means). A
   Page token has no clock on it and plenty of ways to die.

8. Note the Page id from the same response, and verify the token against the edge
   commentdraft actually reads:

   ```
   GET https://graph.facebook.com/v26.0/{page-id}/published_posts
     ?access_token={page-access-token}
   ```

9. Put the Page access token in the environment variable your config will name, in a
   `.env` file next to `config.toml`. Never in `config.toml` itself.

## Configuring commentdraft

Two tables, and most people should write only the first.

```toml
[source]
platform = "facebook"
credential_env = "FACEBOOK_PAGE_TOKEN"
page_id = "1122334455"
```

That is a read-only deployment. It pulls comments, drafts replies, renders the review
page, and **cannot publish anything at all**, because there is no publish credential
anywhere for it to reach. It is the posture to start in: read the drafts for a week
before you ask Meta for a write scope you have not needed yet. A token with only
`pages_show_list`, `pages_read_engagement` and `pages_read_user_content` is enough for
this table and enough for everything up to the review page.

Adding the second table turns `commentdraft publish` on:

```toml
[publish]
platform = "facebook"
credential_env = "FACEBOOK_PAGE_TOKEN"
```

The two `credential_env` values may name the same variable. The tables exist so that
they do not have to. A publish token additionally needs `pages_manage_engagement`.

`page_id` belongs in `[source]`, because reading is what uses it. It is still honoured
in `[publish]` for configs written before `[source]` existed. Publishing never reads it:
a reply goes to the id of the comment it answers. The fallback runs one way only, and
`commentdraft publish` never reads `[source]`, so a token granted for reading cannot
become the token something writes with.

Every key here is checked for shape and never for content. Nothing asks whether
`page_id` names a real Page; a Page id belonging to somebody else surfaces as a
permission error from Meta rather than as a config error from this tool.
`docs/configuration.md` is the full reference for both tables.

## Running the loop

Four commands. Two of them touch Meta.

### Pull

```bash
commentdraft pull --config config.toml --out comments.csv --state pull-state.json
```

Reads the Page's own posts, then the comments on each, and writes the CSV that
`commentdraft run` reads. `--state` is a small JSON file remembering every comment id
handed over so far, which is what stops a scheduled pull from drafting and billing the
same comment twice. Without it, every pull writes everything it can see, and the command
says so on its last line.

`--since` takes an ISO 8601 timestamp such as `2026-08-01T09:30:00+0000`. It is applied
**after** the fetch, on our side, not passed to Meta. The comments edge does document a
`since` parameter, and the connector deliberately does not use it: a server-side filter
that turns out to measure something other than creation time drops rows silently, and
nobody has run this against the live API to find out which it measures. So `--since`
narrows what reaches your CSV and does not reduce a single API call.

Exit codes: 2 is a setup that never reached Meta, 1 is a pull that reached it and did
not come back whole, 0 is clean. A post that could not be read is named on standard
error and costs you exit 1 rather than the whole run; the rows already collected are
still written.

#### What pull reads, and what it leaves out

The connector reads `published_posts`, not `feed`. This matters more than it sounds.
`/feed` returns posts other people made on the Page and posts that merely tag it.
Neither is your content, and replying under a stranger's post from your Page account is
not what anybody configured this for. `published_posts` is the edge that means "what
this Page published".

Comments are read with `filter=stream`. Meta's default is `toplevel`, which returns only
top-level comments, and Meta's own description names the alternative:

> "stream: All-level comments in chronological order. This filter is useful for comment
> moderation tools where it is helpful to see a chronological list of all comments."
>
> <https://developers.facebook.com/docs/graph-api/reference/object/comments/>

The connector also sends `live_filter=no_filter`, and it does nothing on an ordinary
post. Meta's own sentence on that parameter:

> "For comments on a Live streaming video ... In all other circumstances this parameter
> is ignored."
>
> <https://developers.facebook.com/docs/graph-api/reference/v26.0/comment/comments>

It is sent because it costs nothing and a Page that starts streaming should not need a
code change. Earlier drafts of the research behind this page described it as revealing
comments a human moderator can see. It does not, and the test asserting that benefit was
cited as evidence the benefit existed. `filter=stream` is the whole of the correction.

Three things are dropped or kept in ways you should know about before you wonder where a
comment went:

- A comment that arrives carrying a `parent` is a reply to another comment, and it is
  **not queued**. `filter=stream` asks for these by design, Facebook flattens threads, so
  a reply written under a second-level comment comes back parented to the top-level
  comment instead, and the write check reads that as a reply in the wrong place. Offering
  a person a keystroke that cannot work is worse than not offering it. On a busy thread
  this is most of the thread.
- A hidden comment (`is_hidden`) is kept and queued. So is a comment closed to replies
  (`can_comment` false). Both fields are read from the API and there is nowhere in the
  CSV to carry them, and silently discarding a customer's comment because a flag says a
  reply would fail is the worse answer. You find out at the send.
- A comment with no readable id is skipped, which is why this connector does not produce
  the duplicate class `docs/configuration.md` describes for connectors that do.

### Run and review

```bash
commentdraft run --config config.toml --comments comments.csv --out out
commentdraft review out/review.csv --out out
```

Neither touches Meta. `run` calls your model gateway and writes `out/review.csv`;
`review` renders `out/review.html` with a draft banner on it until a person passes
`--approved`.

### Dry run

```bash
commentdraft publish --config config.toml --out out --dry-run
```

This asks for no keystroke, no terminal and **no publish credential**. It does not build
the connector at all. For each drafted reply it prints the platform name, the
`parent_id` the send would carry, the exact text, and the line `dry run, so nothing was
sent`. It does not print a URL or an HTTP request; it prints the arguments the connector
would be handed.

Run this before you grant `pages_manage_engagement`. Reading what would be sent while
holding a token that could not send it is the point of the flag.

### Publish

```bash
commentdraft publish --config config.toml --out out
```

Shows one comment and one draft, waits for a keystroke, and sends that one reply from the
branch that keystroke reaches. There is no `--yes`, no `--all` and no approval column.
Every send appends a line to `out/published.jsonl` carrying the returned id and whether
the reviewer edited the draft. `docs/platform-policy.md` maps that design to the clause
it exists for, including Meta's Developer Policy 1.7.

Exit code 3 is specific to this command: the queue was stopped part way because a write
reached Meta and could not be proved to have done what it says. See
[The reply path](#the-reply-path). 2 is a setup that never ran and 1 is a run that
finished with something refused; a halt is neither, and a scripted caller must not read
them as one event.

## The reply path

This is the part of the Facebook connection nobody else documents, and it is unresolved.

### Meta documents one call as two incompatible things

commentdraft replies to a **comment**, not to a post. Meta's own pages give two answers.

| Source | What it says `POST /{comment_id}` with a `message` does |
|---|---|
| Pages API guide, under the H3 heading "Reply to a Comment" (<https://developers.facebook.com/docs/pages-api/comments-mentions/>, Updated 2026-04-16) | Replies to that comment |
| Comment node reference, under "Updating" (<https://developers.facebook.com/docs/graph-api/reference/v26.0/comment>) | Edits that comment. Parameter `message` is "The text in the new comment message". Return type `Struct { success: bool }` |

Both cannot be true. If a tool follows the guide and the reference is the correct
reading, **every approved reply silently overwrites the customer's comment**, their own
words are gone, and nobody finds out until somebody complains. That is the worst failure
available in this connection, and it is invisible while it is happening.

### Which path the connector takes

`POST /v26.0/{comment-id}/comments` with `{"message": "..."}`, to the comment's own
comments edge.

The documentary weight is on that edge, from one primary page:

> "It is possible for comment objects to have a `/comments` edge, which is called
> **comment replies**."
>
> Publishing, New Page Experience supported objects: "Comments ... PostComment"
>
> "Note, the `can_comment` field on individual comment objects indicates whether it is
> possible to **reply to that comment**."
>
> <https://developers.facebook.com/docs/graph-api/reference/object/comments/>

Two further pieces of evidence say the guide's sample is a rendering defect on that page
rather than a second API. Its documented response is `{"id":"comment_id"}`, described as
"`id` set to the ID for your comment", which is the **Creating** return shape; the
Updating operation returns `Struct { success: bool }`. And the sample immediately above
it, under "Reply to a Post", is `POST /page_post_id` with a `message`, which is
unambiguously the Post edit operation. Two adjacent samples with the identical missing
`/comments` edge, on a page that already eats the slash after `graph.facebook.com`, is
one defect and not two APIs.

Evidence against the edge, stated so you can weigh it yourself: the version-specific edge
reference for `/{comment-id}/comments` says "You can't perform this operation on this
endpoint" under Creating, Updating and Deleting alike
(<https://developers.facebook.com/docs/graph-api/reference/v26.0/comment/comments>). The
same sentence appears on `/{post-id}/comments` and `/{page-post-id}/comments`, both of
which demonstrably accept POST, so the negative is unreliable across the board. And the
Comment node's own Creating section lists only `/{video_id}/comments`. Meta is
inconsistent across three pages about the same edge.

None of this is a live call. It is documentary weight, and documentary weight is what a
runtime check exists to stop being load bearing.

### The invariant, which is what makes this shippable before it is settled

After every write, before anything reports success, the connector proves the write was a
reply:

1. The id returned by the POST is compared against the id it posted to. Equal means the
   call edited the customer's comment. This check needs no second call, so the worst
   outcome is caught even on a run where the read-back itself fails.
2. `GET /v26.0/{returned-id}?fields=id,parent{id},message`.
3. The read-back must return the id we asked for, must carry a `parent`, and that
   parent must be the comment a person approved a reply to. No parent means the reply
   landed on the post as a fresh top-level comment.

Failing 1 ends the run. So does a read-back that cannot be performed or cannot be
parsed: a reply that is live and unproved is not a per-row failure, because if the write
path edits comments it will edit the next one too, and continuing the queue means
damaging the next customer's words while printing a line nobody reads until later.

A reply that landed under the wrong comment, with the parent read back and proved
intact, costs one row instead of the queue. Facebook flattening threads is Meta behaving
as documented rather than this connector destroying anything, and ending a run over it
loses every remaining row for a reason that will recur on the next run.

Comparison of ids allows for both of Facebook's spellings. Facebook writes a comment id
as `98765` and as `1122334455_98765`, and does not promise which one an endpoint hands
back, so the segment after the last underscore is compared as well. A false positive
halts a run and names an overwrite that did not happen, which is recoverable. A false
negative destroys comments quietly. Exact string equality failed in the second
direction.

This check is permanent. It does not come out when somebody confirms the path against a
live Page, because Meta changes edge behaviour between versions and this failure is
silent without it. One extra GET against a human pressing a key per reply costs nothing
anybody can measure.

### What the invariant cost to get right

This is the most useful paragraph on this page for anyone building their own connector.

The first version of the check treated a 2xx response carrying no readable string id as
"nothing happened", raised an ordinary per-row failure, and moved to the next row.

`{"success": true}` is exactly how Graph answers an update.

Driven through the real approval loop with three rows and a transport answering every
POST that way, the result was three POSTs, zero verification GETs, a summary reading
`sent 0, skipped 0, failed 3`, no audit file at all, and the line `not sent` printed
three times. Three comments overwritten while the operator was told nothing had been
sent. The check was sound everywhere it ran and did not run on the response shape the
feared endpoint most plausibly produces.

**A 2xx POST is a write that happened.** An unparseable success is not a non-event.

What the connector does now: a numeric id is read as the id it is, because a JSON
document is allowed to spell `98765` as a number. An answer with no id at all sends the
connector to read the parent comment back, and whatever it finds there the run ends,
either in the overwrite wording when the parent now holds the text just sent, or in the
unproved wording when nobody can say what the write did. Both write an audit line marked
`"verified": false` before the run ends. Nothing retries anywhere on that path, because
one keystroke has to mean at most one POST.

Nothing here is entitled to tell you the customer's comment is intact without having
read it back. Two branches used to say exactly that without looking.

## What breaks, and what each failure means

### Copying Meta's own curl samples

Every sample URL on the Pages API comments guide reads
`https://graph.facebook.comv26.0/...`, missing the slash after `.com`. Three occurrences,
confirmed twice through independent extraction, once with an explicit cache bypass
(<https://developers.facebook.com/docs/pages-api/comments-mentions/>). Pasting one gives
a DNS failure that reads as a network problem on your side. Type the URL rather than
copying it from that page.

### A user token where a Page token belongs

This is the one that costs the most time, because it produces no error.

> "For the following nodes, the `/comments` endpoint returns empty data if you read it
> with a User access token: Album, Photo, Post, Video"
>
> <https://developers.facebook.com/docs/graph-api/reference/object/comments/>

You get `{"data": []}` under HTTP 200. A Page with hundreds of comments reads as a Page
with none. Where a call does fail on it instead, Meta returns error **1705**, which
means the call was made as a person rather than as the Page
(<https://developers.facebook.com/docs/pages-api/comments-mentions/>).

### The error table

The connector reads Meta's code and subcode and prints the sentence you have to act on,
keeping Meta's own message on the end rather than replacing it. Subcodes are looked up on
the subcode alone as well as on the pair, because Meta prints the same token subcodes
under code 190, under code 102, and under a bare `OAuthException` carrying no readable
code.

| Code | Subcode | What it means | What you do |
|---|---|---|---|
| 190 | none | "Access token has expired" | Log in again and exchange a new Page token |
| 190 | 458 | App Not Installed: "User has not logged into your app" | The app was deauthorised. Log in again |
| 190 | 459 | User Checkpointed | Open facebook.com, clear what it asks for, then log in again |
| 190 | 460 | "Password Changed" | Log in again. A password change kills the token |
| 190 | 463 | "Login status or access token has expired, been revoked, or is otherwise invalid" | Log in again |
| 190 | 464 | Unconfirmed User | Confirm the account on facebook.com, then log in again |
| 190 | 467 | Invalid Access Token | Log in again |
| 190 | 492 | "User associated with the Page access token does not have an appropriate role on the Page" | Not a token problem. A new token fails identically. Somebody restores that account's Page role, or at minimum `MODERATE` and `CREATE_CONTENT` |
| 10 | none | "Permission is either not granted or has been removed" | Re-grant. Most likely the 90 day rule below |
| 200 to 299 | none | "Multiple values depending on permission" | Re-grant the `pages_*` scopes and exchange a new Page token |
| 1705 | none | The call was made as a person, not as the Page | Exchange the user token for a Page token |
| 100 | none | A parameter was rejected | Check `source.page_id` against the Page the token was issued for |
| 368 | none | The action was blocked as abusive or disallowed | Stop. Publishing again through it makes the block longer |
| 4, 17, 32, 613, 80001 | none | Rate limits | Back off. See [Limits](#limits) |

Sources: the 190 family, code 10 and the 200 to 299 band are from
<https://developers.facebook.com/docs/graph-api/guides/error-handling>. Codes 4, 17, 32
and 613 are from <https://developers.facebook.com/docs/graph-api/overview/rate-limiting>.
Subcode 492 and codes 100, 368 and 80001 are from the error list on
<https://developers.facebook.com/docs/graph-api/reference/object/comments/>.

### The 90 day rule

> "If your app does not use a permission for 90 days, usually due to user inactivity,
> your app user must regrant your app that permission."
>
> <https://developers.facebook.com/docs/permissions>

This is the most likely reason a working setup stops working with no code change
anywhere.

commentdraft is bursty by design. An operator answers a batch of comments in March,
gets on with their business, and comes back in July to a permission Meta revoked while
nobody was looking. Nothing broke, nothing was edited, no version changed. The symptom is
error code 10, and the fix is walking the login flow again and granting the `pages_*`
scopes, then exchanging a new Page token.

A permission this connector never uses is a permission on the same 90 day clock. A
read-only deployment that later adds `pages_manage_engagement` and does not publish for a
quarter will find that scope gone while reading keeps working.

### A Page that is unpublished

> "If a Page is unpublished no one will be able to comment on a Page post or comment"
>
> <https://developers.facebook.com/docs/pages-api/comments-mentions/>

No comments arrive and no replies can be sent. Nothing in this tool can tell you that
from the outside.

### Retrying

Do not.

> "Continuing to make calls will continue to increase your call count, which will
> increase the time before calls will be successful again."
>
> <https://developers.facebook.com/docs/graph-api/overview/rate-limiting>

Back off on `estimated_time_to_regain_access` from the
`X-Business-Use-Case-Usage` header. The connector itself never retries a write, on a
separate argument: one keystroke has to mean at most one POST.

## Limits

`docs/limits.md` covers what commentdraft cannot do regardless of platform. This section
is what Meta imposes.

### Rate limits

Calling with a Page access token puts you on Business Use Case limits:

> "Calls within 24 hours = 4800 * Number of Engaged Users"
>
> "The Number of Engaged Users is the number of Users who engaged with the Page per 24
> hours."
>
> <https://developers.facebook.com/docs/graph-api/overview/rate-limiting>

Read that formula carefully before assuming headroom. It scales with how busy the Page
is, not with how many followers it has. A Page with three engaged users in a day gets
14,400 calls. A quiet Page gets a budget derived from a very small number, and a handful
of polls can reach it.

Two headers carry your usage. `X-App-Usage` covers platform limits and returns
`call_count`, `total_cputime` and `total_time` as percentages. `X-Business-Use-Case-Usage`
covers the Business Use Case limits and adds `estimated_time_to_regain_access`.
Throttling begins when any of the three percentages reaches 100. Same source.

### Post history

> "The API will return approximately 600 ranked, published posts per year."
>
> <https://developers.facebook.com/docs/graph-api/reference/v26.0/page/feed>

Maximum 100 posts per request. Expired posts are not accessible. A Page with a long or
high-volume history cannot enumerate all of it, so a first pull is not a complete
archive.

### Comments published per day

**Unpublished.** Meta names no per-day ceiling on comments in its developer
documentation. The only documented ceiling is the call budget above, which counts calls
rather than comments. Any specific number you find in a forum is folklore.

The behavioural ceiling is the Community Standards spam policy, which is enforced
without a published number:

> "Posting, sharing, engaging with content or creating accounts, Groups, Pages, Events or
> other assets, either manually or automatically, at very high frequencies."
>
> <https://transparency.meta.com/policies/community-standards/spam/>

The same page adds that restrictions may apply to lower-frequency accounts showing
"other indicators of Spam (e.g., posting repetitive content) or signals of
inauthenticity". That second sentence is the constraint that actually bites here, and it
is not about volume. A model grounded in one source document produces near-identical
replies to near-identical questions, and twenty comments answered with twenty variations
of one paragraph is repetitive content by Meta's own words at any frequency.
`docs/limits.md` explains why nothing in this design can prevent that while a draft is
being written, and what the run report tells you about it afterwards.

### Quota costs per endpoint

**Unpublished.** Meta does not publish per-endpoint point costs for the Pages API the way
some platforms do. Cost is expressed only as a percentage of an opaque budget, in the
two headers above.

### Webhooks

Not built. commentdraft polls. Webhooks would add `pages_manage_metadata`, a public
HTTPS endpoint with a certificate Meta accepts, signature validation on every payload,
and deduplication that Meta explicitly makes your problem. For a command line tool that a
person sits in front of, polling is the smaller thing to own. If you build them yourself,
the field is `feed` rather than a `comments` field, which does not exist for Pages
(<https://developers.facebook.com/docs/graph-api/webhooks/reference/page>).

## What is still unknown

Every item here failed to resolve against a primary source, or cannot resolve without a
live call. None of it is smoothed over above.

**The reply path, empirically.** The whole of
[The reply path](#the-reply-path). One call in the Graph API Explorer against a throwaway
post settles it. Nobody with Page credentials has made that call, and until somebody does,
the runtime check is the answer rather than the documentation.

**Business Verification: which documents are accepted, and how long it takes.** Meta's own
page defers to the Business Help Center
(<https://developers.facebook.com/docs/development/release/business-verification>), and
both Help Center articles returned an empty page shell through every retrieval attempted.
Whether a sole trader without a registered company can verify at all is unknown. This
matters only for the distributed-product path, not for the single-operator path this page
documents.

**How long App Review takes end to end.** One pass is published:

> "It typically takes us less than one week to process your submission, and often takes
> only 2-3 days, but may take longer during peak periods."
>
> <https://developers.facebook.com/docs/app-review/introduction>

That describes one review pass. Rejections are common, screen recordings are the usual
cause, and each resubmission restarts the clock. Meta publishes nothing about how many
passes a submission typically takes, so the end-to-end figure is unpublished and any
number you have seen for it is somebody's anecdote.

**Whether an App Review status change invalidates existing tokens.** No primary statement
was found in either direction. The documented invalidation triggers are the 190 subcodes
and the 90 day rule; losing a permission surfaces as code 10 rather than as a token error.

**Whether Pages API access is free.** No pricing page for Graph API Pages access exists,
no metering documentation exists, and no billing documentation exists. That is an absence
of evidence and not a statement of price. **Meta nowhere says this is free**, and a
platform that has never charged for something is not a platform that has promised not to.
Budget for the possibility that this changes with a version.

**Whether webhook `feed` payloads carry the keys the reference lists.** The Page webhooks
reference enumerates `comment_id`, `parent_id`, `post_id`, `verb`, `item` and the rest as
available properties, and no rendered example payload with `"item": "comment"` was
retrievable from any locale of that page. Irrelevant while commentdraft polls, and the
first thing to capture if anyone builds webhooks.

**Whether comments left through the Comments Plugin are reachable at all.** The claim that
the Graph API cannot reply to them came from a search summary of an archived reference
page rather than from a current primary page. Medium confidence. Check it if any operator
uses the plugin.

**Whether any disclosure of software-assisted reply text is required.** No clause
requiring it was found in the Meta Developer Policies, the Meta Platform Terms, the
Community Standards spam policy or the inauthentic behaviour policy. Absence of a found
clause is not proof of absence. The replies are your own words, published under your own
identity, after your own approval, and `docs/platform-policy.md` covers the transparency
rules this project does build for. Operators in regulated sectors should take their own
advice rather than this page's.

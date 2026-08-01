# X

Reading the replies under posts your account published, and publishing one approved
reply at a time. Nothing on this page is built.

X API v2. There is no dated release train and no version to pin: the path carries `/2/`
and the platform changes underneath it, which is why the dating below is per page rather
than per release. Every `docs.x.com` page cited was read on **2026-08-01**.

No `docs.x.com` page shows a last-updated date on screen, and a widely repeated
conclusion from that is that staleness on this platform is unmeasurable. It is not.
Every page embeds a machine-readable `dateModified` in its JSON-LD:

```bash
curl -s https://docs.x.com/x-api/posts/create-post | grep -o '"dateModified":"[^"]*"'
```

Measured 2026-08-01:

| Page | `dateModified` |
|---|---|
| `/developer-guidelines` | 2026-07-25 |
| `/x-api/getting-started/pricing` | 2026-07-25 |
| `/x-api/fundamentals/rate-limits` | 2026-07-25 |
| `/x-api/getting-started/getting-access` | 2026-07-25 |
| `/changelog` | 2026-07-21 |
| `/fundamentals/authentication/oauth-2-0/authorization-code` | 2026-06-11 |
| `/x-api/posts/create-post` | 2026-05-13 |
| `/x-api/users/get-mentions` | 2026-05-05 |

Run that command before you trust anything here. `create-post` is the interesting row:
untouched since 2026-05-13, which is one explanation for why it still says nothing about
the write restriction introduced on 2026-02-23. See [The reply path](#the-reply-path).

Two hosts refuse automated fetches. `developer.x.com` answers HTTP 402 and `help.x.com`
and `devcommunity.x.com` answer HTTP 403. Text attributed to `help.x.com` below was read
through the Wayback Machine and the snapshot id is given each time.

X writes some of these sentences with a dash. This page is ASCII, so a dash inside a
quotation is rendered as a comma. Nothing else inside a quotation is altered. No word has
been removed from any quotation on this page.

## What this gets you, and what it costs

**commentdraft has one connector and it is Facebook.** There is no X connector: no
module, no registered name, nothing to configure, and nothing on this page describes
software you can run. `docs/platforms/facebook.md` is the connection that exists. This
page is the research for a second one and an account of the state it is in.

The received wisdom about X is that money is the barrier. That was true and it is now
out of date. The tier ladder was replaced by metered pay-per-use on 2026-02-06, and at
commentdraft's shape of workload the bill is roughly **three dollars a month**. The
$100, $200 and $5,000 figures that still dominate search results are prices for a product
X no longer sells. See [Cost](#cost).

What replaced it is worse, because it has no clock on it. Getting API keys is self-serve
and takes minutes. Deploying a tool that drafts replies is not self-serve: **two
independent primary sources require prior written approval from X before AI-generated
replies are deployed**, and neither publishes a turnaround, a queue position or an appeal.
See [The approval that has no queue](#the-approval-that-has-no-queue). A review with a
published SLA is something you can wait for. This is not that.

| Cost | Where it lands |
|---|---|
| Prior written approval is required before deploying AI-generated replies | No published turnaround and no self-serve path. See [The approval that has no queue](#the-approval-that-has-no-queue) |
| The write path may be closed to this use case entirely | A programmatic reply is permitted only when the author "summoned" you, and nobody has established whether a reply to your own post counts. See [The reply path](#the-reply-path) |
| Enterprise is the fallback and has no published price | "Contact sales for high-volume pricing" (<https://docs.x.com/enterprise-api/getting-started/pricing>). For a sole operator that reads as no |
| Everything is metered per resource | About $3 a month at 500 comments read and 250 replies published. See [Cost](#cost) |
| The signup free-text fields are contractual | "Your use case description is binding on you" (<https://docs.x.com/developer-terms/policy>) |
| X keeps an audit right | "X may audit your compliance up to once per year" (<https://docs.x.com/developer-guidelines>) |

## What is verified here, and what is not

**Nobody has run anything against the X API.** No connector exists to run, no credential
has been issued, and not one sentence below reports observed behaviour. The endpoint
paths, scope strings, rate limits and prices were read from X's own documentation and
nothing more than that.

Verified against X's live documentation, read 2026-08-01:

| What | How far the check went |
|---|---|
| Endpoint paths, HTTP methods, request bodies | Read on the reference page for each endpoint |
| OAuth 2.0 scope strings | Read character for character on the authorization-code page and on each endpoint reference |
| Rate limit numbers | Read on <https://docs.x.com/x-api/fundamentals/rate-limits> |
| Prices | Read on <https://docs.x.com/x-api/getting-started/pricing>, including the inline calculator, and cross-checked against the changelog entry that set them |
| Quoted policy text | Quoted from the page named beside it, from raw HTML rather than from a summary, with the date read |
| Page staleness | Taken from each page's JSON-LD `dateModified`, not from prose |

Not verified, and this list is the part of the page that decides whether any of the rest
matters:

- Whether replying to a comment on your own post satisfies the "summoned" test. This is
  the single question that decides whether the platform is usable. See
  [The reply path](#the-reply-path).
- Whether a drafting tool with per-reply human approval falls inside X's prior-approval
  requirement for AI-generated replies. Neither source addresses a human in the loop.
- How long X takes to answer the Policy Support form. Nothing is published.
- Whether the mentions timeline returns replies that do not textually @mention you.
- How far back the mentions timeline reaches.
- Whether an app must sit inside a Project for v2 write endpoints, and whether changing
  app permissions requires minting a fresh token. Both appear only in forum thread
  titles on a host that refuses fetches.
- Whether OAuth 2.0 refresh tokens rotate.
- How long an access token lives. Two X pages contradict each other.

Anything that could not be established at all is under
[What is still unknown](#what-is-still-unknown) rather than smoothed into the prose above
it.

## The approval that has no queue

Two primary sources say the same thing, and the first one was quoted four times by
earlier research that missed it.

**Source A**, <https://docs.x.com/developer-guidelines>, `dateModified` 2026-07-25, under
the heading "Gray areas explained", subsection "AI-Generated Content & Replies". The
whole subsection is a four-item list:

> - "Requires prior approval from X before deployment"
> - "Must still follow all rules (no unsolicited mentions, properly labeled)"
> - "Contact X via the Policy Support form before launching"
> - "Even with approval, cannot impersonate humans"

followed by one sentence:

> "Deploying AI-generated replies without approval is a violation, even if the content
> itself is helpful."

The same page carries a table of scenarios. Two adjacent rows, X's table quoted as X
writes it. The Allowed column is an icon in the original, named here in words:

> | Scenario | Allowed | Why |
> |---|---|---|
> | App auto-replies to users who reply to your post | Checkmark | User engaged first, limit 1 reply. Conditions apply |
> | AI-powered app generates and posts replies | Warning | Requires prior approval from X |

The first row is the one that gets quoted everywhere. The second row sits directly
underneath it, and the two together are what makes the approval requirement inescapable:
the permitted case turns on a person having engaged first, and the drafting is what moves
you into the row below.

**Source B**, <https://help.x.com/en/rules-and-policies/x-automation>, section II.B.3,
"AI-Powered Automated Replies". That host answers HTTP 403 to any automated fetch, so
this was read through the Wayback Machine, snapshot `20260622035529`; the archived page
stamps itself "Updated April 2026". Both sentences, because the first one is the
permission and the second one is its price:

> "Provided you comply with all other rules, you may leverage artificial intelligence
> (AI) technologies to create automated reply bots that generate dynamic, context-aware
> responses, as these can enhance user engagement, provide timely assistance, and foster
> innovative interactions on X. However, to safeguard user experience, prevent potential
> misuse, and ensure alignment with our rules, the deployment or operation of any AI
> reply bot requires prior written and explicit approval from X. Contact your dedicated
> point of contact or submit a request through the developer portal for review."

X permits the category outright. What it withholds is the launch, and it withholds it
until somebody at X says yes in writing.

The same page adds:

> "Note: Advertisers, publishers, and brands using auto-response campaigns must request
> approval from X and may be subject to additional rules."

### Whether this applies to commentdraft

Genuinely arguable, and unsettled. Both sources describe systems that generate and post.
commentdraft generates and a person approves each reply at a keyboard before anything is
sent, one reply per keystroke, with no `--yes` and no `--all`. Neither source addresses
that design in either direction.

The argument that it does not apply: the text everywhere reads as being about accounts
that publish without a human. The argument that it does: the words are "AI-generated
replies", the replies are AI-generated, and the sentence attaches the requirement to
deployment rather than to a degree of automation.

What to do about it, in order:

1. Settle [The reply path](#the-reply-path) first, with one API call. If the write path
   is closed, the approval question never arises.
2. Write to X through the Policy Support form before deploying anything. Describe the
   human approval step in the same words the tool uses, because whatever you write is
   also the use case description that binds you afterwards.
3. Keep the answer. There is no published turnaround to plan around, so treat the wait
   as unbounded and do not commit a delivery date to anyone on the strength of it.

Contrast with Facebook, where a single operator creating their own app needs no App
Review, nothing is queued and nobody at Meta reads anything. On X the credentials are
faster and the permission is slower, and the permission is the part with no number
attached to it.

## Before you start

| You need | You do not need |
|---|---|
| An X account, the one that will publish | A business account. X has no account type that gates API access |
| A payment method on the Developer Console. There is no general free tier | A verified identity or a linked domain, neither of which is stated anywhere |
| An app you create yourself, attached to a Project | A public HTTPS endpoint, unless you build webhooks |
| App permissions set to Read and Write **before** the token is minted | X Premium, which no page states either way. See [What is still unknown](#what-is-still-unknown) |
| Written approval from X, if the requirement above applies to you | Any hosting at all |
| Python 3 and commentdraft installed | A connector, because there is not one |

## Getting access

commentdraft ships no login helper for X, and would not, because there is nothing to
hand the token to. Perform the exchange yourself and keep the result.

1. Sign in at <https://console.x.com> with the X account that will publish.

2. Review and accept the Developer Agreement and Policy
   (<https://docs.x.com/x-api/getting-started/getting-access>).

3. Complete your profile. X's own wording for this step is "Provide basic information
   about how you'll use the API." That text is contractual. See
   [Policy constraints](#policy-constraints) before you type it.

4. Click "New App" and enter the app details: name, description, and use case. The use
   case field is contractual on the same clause.

5. Attach the app to a Project. This is **not** stated on the getting-access page. It
   appears in forum thread titles as a cause of the 403 described under
   [What breaks](#what-breaks-and-what-each-failure-means), on a host that refuses
   fetches, so treat it as plausible and unconfirmed rather than as documented.

6. Set the app's permissions to Read and Write. Do this before step 8, not after: the
   longstanding behaviour is that changing permissions does not upgrade a token that was
   already issued. Also unconfirmed on a current primary page.

7. Generate credentials. You get an API Key and Secret, a Bearer Token, an Access Token
   and Secret, and a Client ID and Secret. X's own instruction on the same page: "Save
   immediately. Credentials are only displayed once."

8. Add credits and set a spending limit in the Developer Console before the first billed
   call.

9. Run the OAuth 2.0 authorization code flow with PKCE
   (<https://docs.x.com/fundamentals/authentication/oauth-2-0/user-access-token>):

   ```
   authorize  https://x.com/i/oauth2/authorize
              ?response_type=code&client_id=...&redirect_uri=...
              &scope=...&state=...&code_challenge=...&code_challenge_method=S256
   token      https://api.x.com/2/oauth2/token
   revoke     https://api.x.com/2/oauth2/revoke
   ```

   Request exactly these scopes, character for character:

   ```
   tweet.read
   users.read
   tweet.write
   offline.access
   ```

   `offline.access` is what yields a refresh token: "Stay connected to your account until
   you revoke access."
   (<https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code>). Add
   `tweet.moderate.write` ("Hide and unhide replies to your Tweets") only if you intend
   to hide anything. App-only Bearer auth cannot write, because writing is user-context.

10. Put the token in an environment variable named by your config, in a `.env` file next
    to `config.toml`. Never in `config.toml` itself.

### How long the token lasts

Two X pages disagree, both live on 2026-08-01. The authorization-code page says an access
token is valid for two hours unless `offline.access` was used. The OAuth FAQ says:

> "Access tokens are not explicitly expired. An access token will be invalidated if a
> user explicitly revokes an application in their X account settings, or if X suspends an
> application."
>
> <https://docs.x.com/resources/fundamentals/authentication/faq>

Build for two hours. The FAQ sentence describes OAuth 1.0a behaviour and reads as
surviving text. Store the refresh token, refresh on a 401 rather than on a timer, and
persist whatever refresh token comes back, because whether they rotate is undocumented.

## Configuring commentdraft

There is nothing to configure. Writing `platform = "x"` into either table is refused
before a credential is asked for, by both commands that reach a connector:

```
unknown platform: x. registered: facebook
```

`commentdraft pull` and `commentdraft publish` each make that check first, so the refusal
costs nothing and names what does exist. `docs/configuration.md` is the reference for the
`[source]` and `[publish]` tables.

What is usable today is the half of the tool that never touches a platform.
`commentdraft run` reads a CSV and `commentdraft review` renders a page from its output,
and neither knows where a row came from. Comments exported from X by hand into the
columns `docs/comments-csv.md` names go through both without a connector existing:

```bash
commentdraft run --config config.toml --comments comments.csv --out out
commentdraft review out/review.csv --out out
```

Sending is the part that needs the connector, and there is no way to send an approved
reply to X from this tool.

## Reading comments

X has no comment object. A comment under your post is a Post whose `conversation_id` is
your post's id, which means there is no "list the comments on my post" endpoint and you
reconstruct the queue from a general-purpose surface. Two are worth using and they differ
by 5x in price.

### The mentions timeline

```
GET https://api.x.com/2/users/{id}/mentions
```

> "Retrieves a list of Posts that mention a specific User by their ID."
>
> <https://docs.x.com/x-api/users/get-mentions>

Scopes `tweet.read` and `users.read`. `max_results` is minimum 5 and maximum 100. Auth
accepts a Bearer Token, an OAuth 2.0 user token, or OAuth 1.0a.

Two reasons to prefer it. It is on X's Owned Reads list, so it bills at $0.001 per
resource instead of $0.005. And every item it returns is by construction a Post that
mentions you, which is the condition the write side tests for. A queue sourced from
search carries no such property.

### Recent search by conversation

```
GET https://api.x.com/2/tweets/search/recent?query=conversation_id:{post_id}
```

> "Retrieves Posts from the last 7 days matching a search query."
>
> <https://docs.x.com/x-api/posts/search-recent-posts>

`conversation_id` is a standalone operator, which X's operator reference defines as one
that "Can be used alone or with any other operators", and lists as
`conversation_id:` / Standalone / "Matches Posts in a conversation thread" with the
example `conversation_id:1334987486343299072`
(<https://docs.x.com/x-api/posts/search/integrate/operators>). X's own request-shaped
example is `https://api.x.com/2/tweets/search/recent?query=conversation_id:1234567890`
(<https://docs.x.com/x-api/fundamentals/conversation-id>). Scopes `tweet.read` and
`users.read`.

The window is seven days and it is hard. A tool that goes quiet for eight days has lost
that period unless it pays for `GET https://api.x.com/2/tweets/search/all`, which is
documented as "Available to pay-per-use and Enterprise customers"
(<https://docs.x.com/x-api/posts/search/introduction>) and bills at the same $0.005.

Two X pages disagree on the maximum `query` length: the endpoint reference says 1 to 4096
characters, the rate limits page notes 512 against the same endpoint. Build to 512 and
you are inside both.

### Webhooks

Not the route for a command line tool, and the obvious answer is the deprecated one.

> "The Account Activity API (AAA) is being deprecated. Check out the X Activity API (XAA)
> for real-time user activity delivery going forward."
>
> <https://docs.x.com/x-api/account-activity/introduction>

Anything on the internet referencing `tweet_create_events` is the retired product. The
current one subscribes with `POST /2/activity/subscriptions` and the event type that
matters here is `post.mention.create`, filtered by `user_id`. Self-serve accounts get a
ceiling of 1,500 subscriptions
(<https://docs.x.com/x-api/activity/introduction>).

The cost of that route is a permanently reachable HTTPS endpoint. X sends a CRC challenge
on registration, hourly thereafter, and on manual revalidation; you answer with
`{"response_token": "sha256=<base64_encoded_hmac_hash>"}` HMAC'd with the consumer secret
rather than a bearer token. Fail it and the webhook is marked `invalid` and "event
delivery stops" (<https://docs.x.com/x-api/webhooks/quickstart>). A laptop that sleeps
through an hourly heartbeat is a dead subscription. Polling the mentions timeline costs
less and owns less.

## The reply path

### The endpoint

```
POST https://api.x.com/2/tweets
```

```json
{
  "text": "...",
  "reply": {
    "in_reply_to_tweet_id": "<the id of the post being replied to>"
  }
}
```

Scopes `tweet.read`, `tweet.write`, `users.read`
(<https://docs.x.com/x-api/posts/create-post>). `in_reply_to_tweet_id` is required inside
`reply`. Two optional fields sit beside it: `auto_populate_reply_metadata`, and
`exclude_reply_user_ids`, "A list of User Ids to be excluded from the reply Tweet".

`quote_tweet_id` is unavailable. The endpoint page states that quote-posting "requires an
Enterprise plan. It is not available on self-serve (pay-per-use) tiers", and the
2026-04-16 changelog entry is a second source for the same fact: "Following, Likes, and
Quote-Posts via the API have been removed from all self-serve tiers."

### The restriction that is not on the endpoint page

On 2026-02-23 X published a changelog entry titled "Addressing LLM-generated spam". In
full, from <https://docs.x.com/changelog>:

> "Today, we made changes to reduce automated, low-quality replies on X. Programmatic
> replies via `POST /2/tweets` are now only permitted when the original Post's author has
> "summoned" the replier (by @mentioning that account or quoting one of its Posts).
> Additional restrictions apply to programmatically @mentioning or quoting users. These
> changes affect self-serve tiers only, Enterprise access is not impacted."

X's own developer account said it in plainer words:

> "To help address automated reply spam, programmatic replies via POST /2/tweets are now
> restricted for X API. You can only reply if the original author @ mentions you or
> quotes your post. Non-replies will remain unchanged. Applies to Free, Basic, Pro,
> Pay-Per-Use."
>
> @XDevelopers, <https://x.com/XDevelopers/status/2026084506822730185>

**Nothing on <https://docs.x.com/x-api/posts/create-post> mentions this.** The only
occurrence of the word "summoned" on that page is inside the JavaScript of the shared
pricing widget. A reader working from the endpoint reference will build the whole write
path and meet the restriction at runtime, as a 403 that names six other things it could
have been. That page's `dateModified` is 2026-05-13, three months after the rule.

### The question nobody could answer

Read the rule against this use case. The "original Post" is the comment sitting under
your post. Its author is the commenter. Did the commenter summon you?

On X, a reply to your post carries you as a mentioned user, which is exactly why that
reply lands in your mentions timeline. So the answer should be yes, and this should be
the case the restriction was written to leave open.

**X has never said so.** The changelog entry has no carve-out text, no error code and no
worked example. The endpoint reference is silent. Developers asked the question directly
on X's own forum in a thread titled "Restricting Programmatic Replies - Does this affect
replying to itself?" and that host answers 403 to every automated fetch, so no official
answer could be retrieved from it. Neither the research behind this page nor the
adversarial check that corrected it settled the question, and the check declined to make
a live call because it would have posted publicly from an account it did not own.

One piece of supporting evidence, stated so you can weigh it yourself and not stronger
than it is: X's pricing page carries a distinct billing category, "Post: Create
(summoned)", at $0.010, and separately exempts summoned replies from the URL surcharge
that applies to every other created Post. A platform that meters summoned replies as a
first-class cheaper category is a platform that expects them to happen. That is an
inference from a rate card, not a statement of the rule.

### How to settle it

It takes one API call and about a cent.

1. Post something ordinary from the operator account.
2. From a second account, reply to it. That reproduces the exact shape of the queue: a
   comment under your own post.
3. Through the API, with a user token holding `tweet.write`, `POST /2/tweets` with
   `reply.in_reply_to_tweet_id` set to the id of that reply.
4. Record the HTTP status and the body verbatim, whichever way it goes.

A 201 means the write path is open and the rest of this page is worth acting on. A 403
means self-serve is closed to this use case and Enterprise, at an unpublished negotiated
price, is the only remaining route. Do this before writing a line of connector code and
before asking X for anything, because it is the cheaper of the two open questions to
close and it can make the other one moot.

## Cost

Prices read from <https://docs.x.com/x-api/getting-started/pricing> on **2026-08-01**,
page `dateModified` 2026-07-25. Re-read it before you budget anything: this platform
changed its commercial model twice in the twelve months before that date.

| Action | Unit cost |
|---|---|
| Posts: Read | $0.005 per resource |
| Owned Reads | $0.001 per resource |
| Post: Create | $0.015 per request |
| Post: Create (with URL) | $0.200 per request |
| Post: Create (summoned) | $0.010 per request |
| Interaction: Delete | $0.010 per request |
| Content: Manage | $0.005 per request |

### The URL surcharge does not apply to summoned replies

This correction matters because the arithmetic built on the other reading is off by a
factor of twenty. From the inline pricing calculator on the pricing page, which also
renders on the create-post page:

> "Posts containing a URL: $0.200 per request (summoned replies remain at standard
> price)."

And the 2026-04-16 changelog entry, whose parenthetical attaches to the URL clause rather
than to the base rate:

> "`POST /2/tweets` is now $0.015 per post, and Posts containing a URL are $0.20 per Post
> (summoned replies remain $0.01)."
>
> <https://docs.x.com/changelog>

So a summoned reply carrying a link back to the source document costs $0.010, the same as
one without. Earlier research read the surcharge as applying to every reply, produced a
worst case of roughly $52.50 a month, and advised designing reply templates to avoid
links. Both were wrong, and wrong in the direction that made the platform look dearer
than it is.

The surcharge is real for a Post that is not a summoned reply. It is one more thing riding
on the unresolved question in [The reply path](#the-reply-path).

### What a month costs

500 comments read and 250 replies published:

| Path | Unit | Volume | Monthly |
|---|---|---|---|
| Read via `/2/users/{id}/mentions`, Owned Read | $0.001 | 500 | $0.50 |
| Read via `search/recent` | $0.005 | 500 | $2.50 |
| Write, summoned, with or without a link | $0.010 | 250 | $2.50 |
| Write, not summoned, no link | $0.015 | 250 | $3.75 |
| Write, not summoned, with a link | $0.200 | 250 | $50.00 |

Roughly **$3.00 a month** on the mentions-plus-summoned path, correct on 2026-08-01.
Ten times that volume is about $30 a month and stays well inside the read cap below.

Two ways that bill grows without an error being raised.

Owned Read pricing is conditional. X's wording is that the endpoints qualify "when `{id}`
matches the authenticated user and that user is the owner of the developer app". An agency
that owns the app while a client authenticates does not meet the second condition, and
every read costs 5x with no warning and no error, only a larger invoice.

Deduplication runs per UTC day:

> "All resources are deduplicated within a 24-hour UTC day window. If you request and are
> charged for a resource (such as a Post), requesting the same resource again within that
> window will not incur an additional charge."
>
> <https://docs.x.com/x-api/getting-started/pricing>

Polling every ten minutes therefore does not bill every ten minutes. Polling across UTC
midnight re-bills everything still in the window, so persist seen ids and pass `since_id`.
For the connector that does exist, `commentdraft pull --state` is that persistence, and an
X connector would need the same file doing the same job for a second reason: money as well
as duplicate drafts.

### The ceiling and the fallback

> "Pay-per-usage plans are capped at 2 million Post reads per monthly billing cycle. If
> you need higher volume, upgrade to an Enterprise plan."
>
> <https://docs.x.com/x-api/getting-started/pricing>

Enterprise has no published price. <https://docs.x.com/enterprise-api/getting-started/pricing>
says "Contact sales for high-volume pricing", describes plans as "custom-tailored to your
organization's needs", and names the pricing model as "Custom contract".

## Policy constraints

Two documents govern and you are bound by both: the automation rules on `help.x.com` and
the Developer Policy and Developer Guidelines on `docs.x.com`.

### The automation rules

The clause everyone quotes is a four-item bulleted list, not the running prose it usually
appears as. Read through the Wayback Machine, snapshot `20260622035529`, because
<https://help.x.com/en/rules-and-policies/x-automation> answers 403 to automated fetches:

> "However, you may send automated replies or mentions to X users so long as:
>
> - in advance of sending the automated reply, the recipient or mentioned user(s) have
>   requested or have clearly indicated an intent on X to be contacted by you (i.e. opted
>   in), for example by replying to a post from your account, or by sending you a Direct
>   Message;
> - you provide a clear and easy way for such users to opt-out of receiving automated
>   replies and mentions, and promptly honor all such opt-out requests;
> - you only send one automated reply or mention per user interaction; and
> - the automated reply or mention is a reply to the user's original post (if your
>   campaign is based on users posting a reply to your post)."

The page stamps itself "Updated April 2026" with no day. The "April 10, 2026" precision
in circulation came from a search snippet and is not on the page.

"For example by replying to a post from your account" is X's own worked example of
opting in, and it is the trigger this tool is pointed at. Three obligations fall out of
the list, and the third one is a gap:

1. One reply per user interaction. A second reply in the same branch needs a fresh
   interaction from that person. Nothing in commentdraft counts interactions.
2. The reply has to be a reply rather than a standalone mention, which means
   `reply.in_reply_to_tweet_id` on every send.
3. An opt-out has to exist and be honoured promptly. **commentdraft keeps no suppression
   list.** There is no per-author state anywhere in the tool, nothing reads opt-out
   phrases, and `--state` remembers comment ids so they are not drafted twice, not people
   who asked to be left alone. Any X connector has to close that before anyone publishes
   through it.

The same page adds that "a user following your account is not on its own a sufficient
indication of user intent to receive an automated response."

### Duplicates

From the Developer Policy, <https://docs.x.com/developer-terms/policy>:

> "The use of the X API and developer products to create spam, or engage in any form of
> platform manipulation, is prohibited."

and, from the same policy family:

> "You may not post duplicative or substantially similar posts on one account or over
> multiple accounts you operate."

That second sentence is the one that bites here, and it is not about volume. Every draft
is grounded in one source document, so thirty people asking the same question receive
thirty variations of one paragraph. `docs/limits.md` explains why nothing in this design
prevents that while a draft is being written, and what the run report says about it
afterwards.

### Data handling

The Developer Guidelines introduce these as "legally binding under the Developer
Agreement" (<https://docs.x.com/developer-guidelines>):

| Trigger | Deadline |
|---|---|
| X requests deletion | 24 hours |
| A user requests deletion | 24 hours |
| Content is suspended or removed on X | 24 hours |
| Your API access is terminated | 10 business days to delete all X data |

commentdraft writes comment text into `comments.csv`, `out/review.csv`,
`out/review.html`, `out/published.jsonl` and the pull state file. Meeting a 24-hour
deletion deadline means a person finding and removing rows from those files the same day.
Nothing in the tool does it and nothing in the tool knows a deletion was requested.

Three more from the same page, each directly relevant to a tool that runs a model over
inbound comments:

- "AI/ML training | Prohibited (except for Grok)." commentdraft refuses to load a config
  that does not set `params.provider.data_collection = "deny"`, which exists for this
  class of reason; `docs/platform-policy.md` covers what that setting is and is not.
- You cannot "derive, infer, or store" information about X users across health, financial
  status, political, racial or ethnic, religious, sex life or orientation, trade union and
  criminal categories. A model reading arbitrary inbound comments will encounter all of
  them.
- "Multiple apps for same use case | Prohibited, don't create duplicate apps to bypass
  limits." Also: "Commercial use | Requires appropriate paid tier; free tier is
  non-commercial only."

Redistribution has ceilings too: 1.5 million Post ids per 30 days to a single entity, and
50,000 hydrated Posts or Users per recipient per day.

### The "Automated" account label

The labelling requirements in the Developer Guidelines are written for accounts that
publish without a person. The same section opens with a carve-out:

> "If you're building an analytics dashboard, research tool, or other non-automated app,
> these labeling requirements don't apply to you, but the technical restrictions still
> do."

Whether an account whose every reply was approved by a human at a keyboard sits inside or
outside that carve-out is not settled by any text found on any page. This page does not
assert an answer in either direction. Treat it as a judgement call for the operator, and
note that the supporting help page on automated account labels reports a last update of
2025-06-23, over a year before the AI-reply rules that now sit beside it.

### Your use case is the contract

> "Your use case description is binding on you, and any substantive deviation from it may
> constitute a violation of our rules and result in enforcement action."
>
> <https://docs.x.com/developer-terms/policy>

Developers must also notify X of any substantive modification and receive approval. That
makes steps 3 and 4 of [Getting access](#getting-access) load bearing. Describe what the
tool does: drafting replies to comments on your own posts, for human review and approval
before anything is published. Marketing copy pasted into that field is a description you
will be held to and cannot meet.

Finally, from the same document family: non-API automation, meaning browser scripting or
scraping of any kind, carries permanent suspension. There is no informal route around any
of the above.

## What breaks, and what each failure means

### The 403 that means six things

A blocked write returns HTTP 403 with "You are not permitted to perform this action". X
returns that same string for at least the following, and the body does not distinguish
them:

1. The reply was not summoned.
2. The app is not attached to a Project.
3. The app's permissions are Read only.
4. The token was minted before the permissions were changed to Read and Write.
5. The account is suspended.
6. The text is over length, or the post's reply settings restrict who may reply.

Causes 2 and 4 are sourced from forum thread titles on a host that refuses fetches, so
they are plausible and unconfirmed. Check them first anyway, because they are the two you
can rule out without spending anything.

### Rate limiting

HTTP 429 with `"code": 88, "message": "Rate limit exceeded"`. Back off on
`x-rate-limit-reset`, which is a Unix timestamp; `x-rate-limit-limit` and
`x-rate-limit-remaining` come back on every response
(<https://docs.x.com/x-api/fundamentals/rate-limits>).

Paying more does not help:

> "Rate limits and billing are separate."
>
> "You can be within rate limits but still incur usage costs, or hit rate limits without
> additional cost."
>
> Same page.

### The token dying quietly

X names two invalidators and no others: a user revoking the application in their account
settings, and X suspending the application
(<https://docs.x.com/resources/fundamentals/authentication/faq>). Whether a password
change, a scope change or an app permission change invalidates a token is addressed by no
page found. The FAQ's own advice is to assume a token may become invalid at any time.

### Reading only the endpoint reference

The two facts most likely to cost a build are absent from the pages a developer naturally
reads. The summoned rule is in the changelog and nowhere else. The prior-approval
requirement is in the Developer Guidelines and the help centre, not in any API reference.
Neither surfaces until deployment.

### Following a tutorial into the retired product

Account Activity API tutorials outnumber X Activity API tutorials by a wide margin and
every one of them is now wrong. `tweet_create_events` is the tell.

## Limits

`docs/limits.md` covers what commentdraft cannot do regardless of platform. This section
is what X imposes.

### Rate limits

From <https://docs.x.com/x-api/fundamentals/rate-limits>, which states its default window
in its own words: "Limits are shown per 15 minutes unless otherwise noted (e.g. "/24hrs"
or "/sec")."

| Method | Endpoint | Per app | Per user |
|---|---|---|---|
| GET | `/2/tweets/search/recent` | 450 / 15 min | 300 / 15 min |
| GET | `/2/users/:id/mentions` | 450 / 15 min | 300 / 15 min |
| GET | `/2/users/:id/tweets` | 10,000 / 15 min | 900 / 15 min |
| POST | `/2/tweets` | 10,000 / 24 hrs | 100 / 15 min |
| DELETE | `/2/tweets/:id` | not published | 50 / 15 min |
| | `/2/activity/subscriptions` | 500 / 15 min | not published |

A person approving one reply at a time will never approach 100 posts in fifteen minutes.
The write ceiling is not the constraint on this design; the two permission questions are.

### Replies published per day

**Unpublished.** X names no per-day ceiling on replies beyond the write rate limits above
and the automation rule of one reply per user interaction. Any specific daily number you
find in a forum is folklore.

### Monthly reads

Two million Post reads per monthly billing cycle on pay-per-use. What actually happens on
reaching it is not published: the post cap page says only that you should consider an
Enterprise plan, and does not say whether requests are refused, throttled or billed
differently.

### Rate limits X does not publish

`PUT https://api.x.com/2/tweets/{tweet_id}/hidden` and `POST /2/webhooks` have no row in
the rate limits table.

### Search lookback

Seven days on `search/recent`, hard. The full archive endpoint reaches back to 2006 and
costs $0.005 per Post.

## What is still unknown

Every item here failed to resolve against a primary source, or cannot resolve without a
live call or a reply from X. None of it is smoothed over above.

**Whether a reply to a comment on your own post is "summoned".** The whole of
[The reply path](#the-reply-path). One API call settles it, nobody has made that call, and
until somebody does the entire platform is conditional on a guess. Everything else on this
page is downstream of it.

**Whether commentdraft's per-reply human approval takes it outside the prior-approval
requirement for AI-generated replies.** Both sources in
[The approval that has no queue](#the-approval-that-has-no-queue) describe systems that
generate and post without a person. Neither addresses a human in the loop. Only X can
answer, through the Policy Support form.

**How long X takes to answer that form.** No SLA, no queue position, no published median.
Absence of a number is not a short wait.

**Whether the "Automated" label applies to a human-approved account.** No text addresses
it. The supporting help page reports a last update of 2025-06-23.

**How long an access token lives.** Two primary pages contradict each other, both live.
No page shows an example token response carrying an `expires_in` value.

**Whether refresh tokens rotate.** Not stated on any OAuth page. Persist the newly
returned one every time.

**Whether an app must be inside a Project for v2 writes, and whether changing app
permissions requires re-minting tokens.** Both appear only in forum thread titles on
`devcommunity.x.com`, which answers 403. The getting-access page says neither.

**How far back the mentions timeline reaches.** The classic figures of 800 mentions and
3,200 own posts appear nowhere in current documentation. The endpoint page states no
limit; a tutorial page says only that timelines reach "older than the last 7 days".

**Whether the mentions timeline includes replies that do not textually @mention you.**
Structurally it should include every reply to your posts, and no page states it. The
quickstart offers an "Exclude replies" option without documenting the default.

**Whether hidden replies still appear in search results or the mentions timeline.** No
primary page addresses it. A connector that re-surfaces a comment the operator
deliberately hid is a defect nobody would look for.

**The per-event price of `post.mention.create`.** The pricing page lists webhook event
prices for `post.create`, `follow.follow`, `dm.received` and `spaces.start` and has no row
for the mention event.

**Whether X Premium is required for API access or for posting through the API.** No
primary page states it either way, and the two hosts that might are the two that refuse
fetches.

**Minimum credit purchase, and whether credits expire.** Neither the pricing page nor the
post cap page states either. "No contracts or minimum spend" on the introduction page is
about commitment, not purchase size.

**Public Utility App eligibility.** The changelog says "Public Utility Apps continue to
receive free scaled access" and publishes no criteria anywhere findable. Assume this tool
does not qualify.

**The maximum `query` length.** 4096 on the endpoint reference, 512 on the rate limits
page, both live. Unresolved.

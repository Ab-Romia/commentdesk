# Threads

Reading the replies to posts a Threads account published, and what stands between an
operator and publishing one approved reply at a time.

The Threads API carries no Graph-style version string on its reply endpoints. The only
version seen on any page read for this document is `v1.0`, on the token debug endpoint.
Both hosts are live and Meta says so itself:

> "The Threads API can be accessed by either `graph.threads.com` or `graph.threads.net`"
>
> <https://developers.facebook.com/docs/threads/overview> (Updated: Dec 22, 2025)

Every page cited below was read on **2026-08-01**. Meta stamps most of its documentation
with its own `Updated:` date, and where that date matters it is given next to the link.

## What this gets you, and what it costs

**There is no Threads connector.** commentdraft ships exactly one connector and it is
Facebook. `commentdraft pull` cannot read Threads and `commentdraft publish` cannot write
to it. Naming Threads in either table fails at the registry lookup, before a credential is
read and before anything is built:

```
unknown platform: threads. registered: facebook
```

This page is the access work done in advance: what the Threads API offers, what being
allowed to call it costs, and what a connector would have to prove before it could be
trusted with a customer's reply. `docs/platforms/facebook.md` documents the connector that
exists.

The API surface is good. Reading replies and publishing a reply are both first-party
documented operations: `GET /{media-id}/conversation` on the way in, and a two-step
container-then-publish `POST` carrying `reply_to_id` on the way out. Neither is a scrape,
a private beta, or a partner programme.

The cost is the access chain, and it has two gates rather than one.

| Gate | What clears it |
|---|---|
| Calling the API at all | An app you create with the Threads use case added, and the account holding a Threads Tester role on that app. Nothing is reviewed and nobody at Meta reads anything |
| Any use by somebody who is not a tester or role holder on your app | App Review on each permission, and a published app |
| App Review for these scopes | The app connected to a Business that has completed Business Verification |

Read the third row before planning around the second. An operator who reads "App Review",
budgets a week and starts recording a screencast is one document set short of being able to
submit at all: Business Verification runs first, it is company paperwork rather than a
demonstration of software, and only a Business admin can complete it. See
[App Review, and the verification behind it](#app-review-and-the-verification-behind-it).

Everything below the token section is the single-operator path, where the operator is the
app's own admin and its Threads Tester. That path clears neither gate because it needs
neither. What it costs instead:

| Cost | Where it lands |
|---|---|
| The permission grant expires 90 days after it was made | Separate clock from the token, and the one that catches people. See [Two clocks](#two-clocks-and-only-one-of-them-is-the-token) |
| A private profile cannot extend a grant by refreshing | A human walks the authorization window again every 90 days, forever |
| The long-lived token expires at 60 days unless refreshed | commentdraft is used in bursts, so a quarter of silence kills both clocks at once |
| The reply publishing quota is 1000 per rolling 24 hours | Not binding at one keystroke per reply. See [Limits](#limits) |
| Reply approvals put incoming replies in a second queue | Two endpoints to poll rather than one, and only when the operator turned approvals on. See [Reply approvals](#reply-approvals-and-the-second-queue) |

## What is verified here, and what is not

**Nobody has called the Threads API.** No connector exists, no credential was held, and no
request was made. Every statement on this page is read off Meta's documentation on
2026-08-01, and not one sentence reports observed behaviour of a live endpoint.

Verified against Meta's live documentation:

| What | How far the check went |
|---|---|
| Endpoint paths and HTTP methods | Read on the Threads reference page for each operation |
| Scope strings | Read on the retrieve-and-manage-replies page and confirmed again on get-started |
| Quota field names and totals | Read on the Overview page, each with its own worked JSON example |
| Token lifetimes and the grant clock | Read on get-started and the long-lived tokens page, then re-read byte for byte |
| Quoted policy text | Quoted from the page named beside it, with the date read |
| The research behind this page | Put through a second adversarial pass that pulled raw page text rather than a summary, and corrected four claims |

Those four corrections are named rather than quietly absorbed, because each one was
confidently wrong in the same direction, which is toward more uncertainty than the pages
actually carry:

1. Pending replies were described as a documentation gap and as something approvable only
   inside the Threads app. Both are wrong. Reply Management states the visibility rule in
   one sentence, and approval is an API call. See
   [Reply approvals](#reply-approvals-and-the-second-queue).
2. The publishing quota field names were marked unverified. All of them are on the
   Overview page with worked examples and totals. See [Limits](#limits).
3. The Meta Developer Policies were given a last-updated date of 3 February 2026. That page
   carries no date at all; 3 February 2026 belongs to the Meta Platform Terms, a different
   document. Section 5's title was also wrong.
4. The Threads Terms of Use were cited at a host that fails DNS resolution from three
   independent resolvers, and the clause quoted was not the one that matters most to a
   business. See [What the terms say](#what-the-terms-say).

Not verified. These are the items that matter, and each settles with a live call rather
than another pass over the documentation:

- Whether a reply held in the approval queue appears in `GET /{media-id}/replies` or
  `GET /{media-id}/conversation` before it is approved. "Hidden until then" implies not.
  No sentence names those two endpoints.
- Whether `reply_to_id` accepts the id of another person's reply. Meta's own parameter
  description calls it a media container id. See [Publishing a reply](#publishing-a-reply).
- Whether the Threads account must be a professional account. No Threads developer page
  read says either way.
- What invalidates a token besides expiry. The debug endpoint reports `is_valid` and no
  page enumerates what flips it.
- Whether a reply hidden through `manage_reply` stays retrievable through the API.
- Whether `GET /{media-id}/conversation` returns `replied_to` and `root_post` on each item.
  Those fields are published for the replies endpoints.
- Whether `threads_content_publish` is required to publish a reply. It is named against the
  reply quota and nowhere else. See [Publishing a reply](#publishing-a-reply).
- Whether the Threads use case can share one app with Facebook Login.

Anything that could not be established at all is under
[What is still unknown](#what-is-still-unknown) rather than smoothed into the prose above
it.

## Where Threads sits relative to Instagram and Facebook

Same App Dashboard, separate product. Threads is documented at its own top level
(`developers.facebook.com/docs/threads/`), authorizes on its own host (`threads.net` and
`threads.com`, not `facebook.com`), and uses its own scope namespace (`threads_*`, not
`instagram_*` and not `pages_*`). No Threads developer page read states a requirement for a
linked Facebook Page.

One app produces two sets of credentials, and picking the wrong pair is the first thing
that goes wrong:

> "When creating your app there will be 2 app IDs and app secrets. For Threads API
> implementation purposes, use the Threads app ID and its corresponding app secret."
>
> <https://developers.facebook.com/docs/threads/get-started/> (Updated: Jun 30, 2026)

The Threads credentials appear once the Threads use case is added:

> "To access the Threads API, create an app and pick the Threads Use Case."
>
> <https://developers.facebook.com/docs/threads/get-started/>

`docs/platforms/instagram.md` covers the two mutually exclusive login routes an Instagram
app has to choose between, and `docs/platforms/facebook.md` covers Page tokens and the
`pages_*` scopes. Neither applies here. Threads documents one route, one scope namespace,
and one token type. What does carry across is the App Review and Business Verification
machinery, which is shared across all three products and is quoted in this page from the
same pages those two cite.

## Before you start

| You need | You do not need |
|---|---|
| A Threads account, kept public. See [Two clocks](#two-clocks-and-only-one-of-them-is-the-token) and [What breaks](#what-breaks-and-what-each-failure-means) | A Facebook Page |
| A Meta developer account, registered with an authentic account (Developer Policy 1.1) | An Instagram professional account, as far as any Threads developer page says |
| An app with the Threads use case added, and the Threads app id and secret from it | A verified business, for the single-operator path |
| A Threads Tester role on that app, accepted from the Threads side | App Review, for the single-operator path |
| A redirect URI you control | A public HTTPS callback, unless you build webhooks |
| Somewhere to run an OAuth exchange by hand | commentdraft, for any of this. There is no connector to configure |

## Getting a token

commentdraft ships no login helper for any platform, and there is nothing here for it to
hand a token to. Perform this exchange yourself, and keep the result somewhere you can
paste it into a request.

1. Sign in at <https://developers.facebook.com/> and register as a developer. Developer
   Policy 1.1: "Develop and manage your App with an authentic account."
   (<https://developers.facebook.com/devpolicy/>)

2. Create an app in the App Dashboard and add the Threads use case. Take the **Threads**
   app id and secret, not the other pair.

3. Add yourself as a Threads Tester:

   > "Invitations can be sent by clicking on the Add People button and selecting Threads
   > Tester in the App Dashboard > App roles > Roles tab"
   >
   > <https://developers.facebook.com/docs/threads/get-started/>

   The invitation is accepted from the Threads side, under Account Settings > Website
   permissions. Until it is accepted, the authorization window will refuse the account.

4. Send the account through the authorization window:

   ```
   GET https://threads.net/oauth/authorize
     ?client_id={threads-app-id}
     &redirect_uri={your-redirect-uri}
     &scope=threads_basic,threads_read_replies
     &response_type=code
   ```

   Add `threads_manage_replies` and `threads_content_publish` only when you intend to
   publish, and read [Publishing a reply](#publishing-a-reply) on why the second of those
   two is an inference rather than a quoted requirement. `threads_basic` is not optional on
   any call:

   > "threads_basic - Required for making any calls to all Threads API endpoints."
   >
   > "threads_read_replies - Required for making GET calls to reply endpoints."
   >
   > "threads_manage_replies - Required for making POST calls to reply endpoints."
   >
   > <https://developers.facebook.com/docs/threads/retrieve-and-manage-replies/>

   `threads.com/oauth/authorize` appears in Meta's own pages for the same flow. Both hosts
   are documented as valid on the Overview page.

   > "Authorization codes are valid for 1 hour and can only be used once."
   >
   > <https://developers.facebook.com/docs/threads/get-started/>

5. Exchange the code for a short-lived token, which lasts 1 hour:

   ```
   POST https://graph.threads.net/oauth/access_token
     client_id={threads-app-id}
     client_secret={threads-app-secret}
     code={code}
     grant_type=authorization_code
     redirect_uri={your-redirect-uri}
   ```

   The response carries `access_token` and `user_id`.
   (<https://developers.facebook.com/docs/threads/get-started/get-access-tokens-and-permissions/>)

6. Exchange that for a long-lived token, valid 60 days, before the short-lived one dies.
   An expired short-lived token cannot be exchanged at all.
   (<https://developers.facebook.com/docs/threads/get-started/long-lived-tokens/>)

7. Refresh the long-lived token on a schedule:

   ```
   GET https://graph.threads.com/refresh_access_token
     ?grant_type=th_refresh_token
     &access_token={long-lived-token}
   ```

   > "Tokens that have not been refreshed in 60 days will expire."
   >
   > <https://developers.facebook.com/docs/threads/get-started/long-lived-tokens/>

   The token must be at least 24 hours old and not yet expired, and the account must still
   hold `threads_basic`. Same page.

8. Read the token back before trusting it:

   ```
   GET https://graph.threads.com/v1.0/debug_token
     ?input_token={token-to-inspect}
     &access_token={a-tester-token}
   ```

   It returns `type`, `application`, `is_valid`, `expires_at`, `data_access_expires_at`,
   `issued_at`, `scopes` and `user_id`. `scopes` is the field to check when a call fails
   for a reason nobody can name.
   (<https://developers.facebook.com/docs/threads/troubleshooting/debug-access-token/>)

9. Put the token in an environment variable in a file that is not in version control.
   Nothing in commentdraft will read it, because nothing in commentdraft speaks to Threads.

## App Review, and the verification behind it

The single-operator path above ends at step 9 and needs nothing in this section. Read it
anyway before building anything other people log into, because the order of the two gates
is the part that ruins timelines.

Gate one. Anybody who is not a tester or role holder on your app cannot grant these
permissions at all until they have been reviewed:

> "In order for app users without a role on your app to be able to grant your app these
> permissions, each permission must first be approved through the App Review process, and
> your app must be published."
>
> <https://developers.facebook.com/docs/threads/get-started/>

> "If your app will be used by anyone without a Role on the app or a role in a Business
> that has claimed the app, it must first undergo App Review."
>
> <https://developers.facebook.com/docs/app-review/>

Gate two, which runs first. A review submission for these permissions cannot be made by an
app that is not attached to a verified Business:

> "Apps that request advanced access for permissions and apps that allow other Businesses
> to access their own data must be connected to a Business that has completed Business
> Verification."
>
> "If your app will only be used by app users who have a role on the app itself you do not
> need to complete verification."
>
> "only someone with an Admin role in the Business will be able to complete the
> verification process"
>
> <https://developers.facebook.com/docs/development/release/business-verification>

> "Business Verification is required to get Advanced Access."
>
> <https://developers.facebook.com/docs/graph-api/overview/access-levels>

So a reader who believes they are one review away is two, and the second one is a document
review of a company rather than a review of software. The verification is completed from
App Dashboard > Settings > Basic > Verification.

A vocabulary warning, because it costs an afternoon. No Threads-specific page read here uses
the words "Standard Access" or "Advanced Access", which is the vocabulary the Instagram and
Facebook pages use for exactly this distinction. The Threads pages describe the same
mechanic (a permission a tester can grant against a permission that has been reviewed)
without naming the tiers. Somebody looking for those two labels on a Threads dashboard
screen may not find them.

Publishing the app is a separate checklist that has to be finished before a submission goes
anywhere: an app icon between 512x512 and 1024x1024 px in JPEG, GIF or PNG and under 5MB, a
privacy policy URL, a data deletion URL with instructions, and, for apps operating in the
EU, Data Protection Officer contact details.
(<https://developers.facebook.com/docs/threads/get-started/create-an-app/>)

One review pass has a published figure:

> "It typically takes us less than one week to process your submission, and often takes
> only 2-3 days, but may take longer during peak periods."
>
> <https://developers.facebook.com/docs/app-review/introduction>

That is one pass, and it presumes verification is already done. Meta publishes nothing about
how many passes a submission takes or how long Business Verification runs. See
[What is still unknown](#what-is-still-unknown).

## Reading replies

Three read endpoints, and the difference between them decides how much of a thread a tool
can see.

| Endpoint | What it returns |
|---|---|
| `GET /{threads-user-id}/replies` | "a paginated list of all replies created by a user", meaning replies the account itself wrote |
| `GET /{media-id}/replies` | Top-level replies under one post |
| `GET /{media-id}/conversation` | "all replies, regardless of the depth, either in chronological or reverse chronological order" |

Sources:
<https://developers.facebook.com/docs/threads/retrieve-and-manage-replies/retrieve-replies/>
and
<https://developers.facebook.com/docs/threads/retrieve-and-manage-replies/replies-and-conversations/>

`/conversation` is the one to poll. It is described as "a paginated and flattened list of
all top-level and nested replies", which removes the walk over `has_replies` that `/replies`
would otherwise force. Both take a `reverse` parameter, default `true`.

Reading needs `threads_basic` and `threads_read_replies`, and nothing else.

The fields published for the replies endpoints are `id`, `text`, `username`, `permalink`,
`timestamp`, `media_product_type`, `media_type`, `media_url`, `shortcode`, `thumbnail_url`,
`children`, `is_reply`, `is_reply_owned_by_me`, `root_post`, `replied_to`, `reply_audience`,
`has_replies`, `is_quote_post` and `quoted_post`.

Two of those are load bearing for anything that drafts replies. `is_reply_owned_by_me`
is how a tool avoids drafting an answer to its own operator's previous reply, which is the
failure that turns a thread into a loop. `replied_to` is how a nested reply is identified as
nested. On Facebook the equivalent question is answered by inference and the connector
refuses the row (`docs/platforms/facebook.md`, under what pull leaves out); the Threads field
list publishes the answer, at least for `/replies`. Whether `/conversation` carries the same
two fields on each item was not confirmed on any page read.

## Reply approvals, and the second queue

Threads has a first-party approval queue for incoming replies, and a tool that polls only
`/conversation` can miss it entirely.

> "You can create posts with reply approvals enabled using the Threads API. Replies to these
> posts must be approved to get published and are hidden until then."
>
> <https://developers.facebook.com/docs/threads/reply-management/> (Updated: Feb 13, 2026)

The queue exists only where the poster asked for it. `enable_reply_approvals=true` is set at
post creation, by the account that owns the post, so an operator who never sets it has no
pending queue on that post and nothing to poll. Meta adds one exclusion: "Reply approvals
cannot be enabled for ghost posts."

Where it is on, both sides are API calls:

```
GET  /{threads-media-id}/pending_replies
POST /{THREADS_REPLY_ID}/manage_pending_reply?approve={true|false}
```

> "The default behavior will return all pending and ignored replies."
>
> <https://developers.facebook.com/docs/threads/reply-management/>

`pending_replies` is filterable on `approval_status`, which takes `pending` or `ignored`, and
each item carries a `reply_approval_status` field. `manage_pending_reply` answers
`{"success": true}`, and an ignored reply can still be approved later.

What no page states is whether a pending reply is excluded from `/replies` and
`/conversation` specifically. "Hidden until then" implies it and a dedicated endpoint exists
for reaching them, which is the shape of an API where the two lists are disjoint. One test
with `enable_reply_approvals` on settles it, and until somebody runs that test, a Threads
connector has to poll both endpoints or document that it cannot see held replies.

Two adjacent moderation calls, for completeness:

- `POST /{THREADS_REPLY_ID}/manage_reply` with `hide={true|false}` hides or unhides a
  top-level reply. "Replies nested deeper than the top-level reply cannot be targeted in
  isolation."
- `reply_control` at post creation restricts who may reply at all, taking `everyone`,
  `accounts_you_follow`, `mentioned_only`, `parent_post_author_only` or `followers_only`.

Both from <https://developers.facebook.com/docs/threads/reply-management/>.

## Publishing a reply

Two calls, and the first one does not publish anything.

Step one creates a container:

```
POST https://graph.threads.net/{threads-user-id}/threads
  media_type=TEXT
  text={the reply}
  reply_to_id={id of the reply being answered}
  access_token={token}
```

Step two publishes it:

```
POST https://graph.threads.net/{threads-user-id}/threads_publish
  creation_id={id returned by step one}
  access_token={token}
```

Both from
<https://developers.facebook.com/docs/threads/retrieve-and-manage-replies/create-replies/>
and <https://developers.facebook.com/docs/threads/reference/publishing/>. `media_type`
accepts `TEXT`, `IMAGE`, `VIDEO` or `CAROUSEL`.

Publishing needs `threads_basic` and `threads_manage_replies`. It very probably needs
`threads_content_publish` as well, and the evidence for that third one is indirect: the
create-replies page names no scope at all, and the only place all three appear together is
the Overview page's quota table, where the reply quota is gated behind `threads_basic`,
`threads_content_publish` and `threads_manage_replies`. A quota gate is not a permission
requirement in so many words. Request all three on a review submission rather than finding
out on the second call.

There is a wrinkle in `reply_to_id` worth knowing before anyone writes code against it.
Meta's own parameter description reads "identifier of the Threads media container created
from the `/threads` endpoint", which describes a container id rather than the id of somebody
else's reply. The operation being documented is answering an existing reply, and the id a
reader has in hand at that moment came out of `/conversation`. Whether the two are the same
namespace is not stated on any page read here, and it is the first thing to establish with a
throwaway post.

A timing note that is a recommendation rather than a guarantee:

> "It is recommended to wait on average 30 seconds before publishing a Threads media
> container to give our server enough time to fully process the upload."
>
> <https://developers.facebook.com/docs/threads/retrieve-and-manage-replies/create-replies/>

For a text reply, polling `GET /{container-id}?fields=status` is the shape that matches what
the sentence actually promises. A fixed sleep of 30 seconds per approved reply is a worse
answer to the same problem.

The ownership rule is the one that gets misread as a scope problem:

> "To reply to a thread, you must meet one of the following permission requirements: You are
> the owner of the root thread post / You have either the `threads_keyword_search` or the
> `threads_manage_mentions` permission."
>
> <https://developers.facebook.com/docs/threads/retrieve-and-manage-replies/create-replies/>

Answering replies under your own posts satisfies the first condition, so neither extra scope
is needed. Answering a mention on somebody else's thread does not, and `threads_manage_replies`
will not rescue it. A tool that grows that feature later hits a wall that reads like a
missing permission and is a missing ownership.

### What a connector would have to prove

Nothing here is a live call, so this is design rather than a report. The Facebook connector
reads back every write and refuses to report success until the reply is proved to be a reply
(`docs/platforms/facebook.md`, under the reply path), and it exists because Meta documents
one Facebook endpoint as two incompatible operations. Threads has no equivalent
contradiction on any page read here. It has a different exposure: a two-step write where the
first call can succeed and the second can fail, leaving a container that is not a reply and
not visible, with an id that looks like a result. A connector that returns the container id
as the published id would be writing an audit line that names something nobody can find. The
id worth recording is the one `threads_publish` returns.

## What commentdraft can do with this today

Reading and drafting, once the comments are in a file. Publishing, by hand.

`commentdraft run`, `commentdraft review`, `commentdraft chat` and `commentdraft bakeoff`
never touch a platform. They read a CSV with these columns and nothing else:

```csv
id,platform,author,comment,post_title
```

Threads reply fields map onto four of them without a decision to make: `id` to `id`,
`username` to `author`, `text` to `comment`, and whatever names the post to `post_title`.
`platform` is a free string that selects nothing, so `threads` is as good a value as any.
`docs/comments-csv.md` is the full format and `docs/configuration.md` is the config
reference for the tables a connector would use if one existed.

What that gets you: drafts, a review page, and a run report, for replies exported by hand.
What it does not get you is any part of the send. `commentdraft publish` reads
`[publish].platform` and there is no value for it that reaches Threads.

## What breaks, and what each failure means

### Two clocks, and only one of them is the token

This is the failure most likely to arrive with no code change anywhere.

> "Permission grants made by app users with public profiles are valid for 90 days.
> Refreshing an app user's long-lived access token will extend the permission grant for
> another 90 days if the app user who granted the token has a public profile. If the app
> user's profile is private, however, the permission grant cannot be extended and the app
> user must grant the expired permission to your app again."
>
> <https://developers.facebook.com/docs/threads/get-started/>

The token expires at 60 days and refreshing resets it. The grant expires at 90 days and
refreshing resets it only for a public profile. A private profile therefore has a hard
90-day ceiling that no amount of automated refreshing moves, and the symptom is a token
whose `debug_token` response says `is_valid` while calls fail on permissions. Build the
re-authorization path on day one; it will be needed.

Keeping the account public is the practical answer, and it is also what the webhook rule
below requires.

### A private account gets no reply notifications, ever

> "Apps don't receive notifications if the media where the reply or mention appears was
> created by a private account."
>
> <https://developers.facebook.com/docs/threads/webhooks> (Updated: Jun 30, 2026)

Not delayed and not degraded. Delete and publish notifications still reach a public account
or a private account that authenticated to the app; reply and mention notifications do not.
Polling `/conversation` is unaffected by this, which is one more reason a first version
should poll.

### Replies held for approval

Covered above. A tool that polls one endpoint on a post with approvals enabled will report
that nobody replied. See [Reply approvals](#reply-approvals-and-the-second-queue).

### The wrong app id

An app with the Threads use case carries two app ids and two secrets. The Threads pair is
the one every Threads call wants. Using the other pair produces an authorization failure at
the very first step, before anything interesting has been attempted.

### Two hostnames

`graph.threads.net` and `graph.threads.com` both work, and so do `threads.net` and
`threads.com` for the authorization window. Meta's own pages alternate between them, and the
Overview page states outright that either host reaches the API. A tutorial using the other
one is not out of date on that basis alone.

### What kills a token

Unknown beyond expiry. No page read here enumerates the conditions that turn `is_valid`
false, which is a real difference from Facebook, where a whole table of subcodes names the
password change, the checkpoint and the revoked login separately
(`docs/platforms/facebook.md`, under the error table). For Threads, treat every
authorization failure as "go and re-authorize", because nothing published lets you
distinguish the causes.

## Limits

`docs/limits.md` covers what commentdraft cannot do regardless of platform. This section is
what Threads imposes.

### Rate limits

> Calls within 24 hours = `4800 * Number of Impressions`
>
> Total CPU time = `720000 * number_of_impressions`
>
> Total time = `2880000 * Number of Impressions`
>
> <https://developers.facebook.com/docs/threads/overview>

The impressions floor is what makes this survivable on a quiet account:

> "the minimum value for impressions is 10"
>
> <https://developers.facebook.com/docs/graph-api/overview/rate-limiting/>

That floor is in the Threads section of the rate limiting page and it is not in the
Instagram section, which is a real difference between the two products rather than an
extraction artifact. A Threads account with no impressions at all still gets a budget
computed from 10.

### Publishing quotas

One endpoint reports all of them:

```
GET https://graph.threads.net/{threads-user-id}/threads_publishing_limit
```

| Field | Config field | Total | Window | Scopes it sits behind |
|---|---|---|---|---|
| `quota_usage` | `config` | 250 | 86400 | `threads_basic`, `threads_content_publish` |
| `reply_quota_usage` | `reply_config` | 1000 | 86400 | `threads_basic`, `threads_content_publish`, `threads_manage_replies` |
| `delete_quota_usage` | `delete_config` | 100 | 86400 | `threads_basic`, `threads_delete` |
| `location_search_quota_usage` | `location_search_config` | 500 | 86400 | `threads_basic`, `threads_location_tagging` |

Meta's own wording for the reply pair:

> `reply_quota_usage` - "Threads reply publishing count over the last 24 hours."
>
> `reply_config` - "...contains the `quota_total` and `quota_duration` fields."
>
> `"reply_config": { "quota_total": 1000, "quota_duration": 86400 }`
>
> <https://developers.facebook.com/docs/threads/overview>

Every row above is on that page with a worked JSON example beside it. The research behind
this document listed three of the four field names as unverified guesses from a search
summary; they are published, and the totals are published with them.

At one keystroke per reply, 1000 replies per 24 hours is not a ceiling anybody reaches. It
is here so that a reader running a high-volume account knows where the number lives and how
to read current usage rather than inferring it from failures.

### Deletions

100 per 24 hours, which is a tenth of the reply quota. A tool that publishes replies and
then deletes them during testing runs out of deletions long before it runs out of replies.

### Comments published per day

The reply quota above is the only published per-day ceiling, and it counts API-published
replies rather than replies to a specific post. The behavioural ceiling is the Community
Standards spam policy, enforced without a published number and quoted in
`docs/platforms/facebook.md`. The clause that bites here is not about volume: near-identical
replies to near-identical questions are repetitive content by Meta's own words at any
frequency. `docs/limits.md` explains why nothing in this design prevents that while a draft
is being written, and what the run report says about it afterwards.

### Cost

**Unpublished.** No pricing page, no tier structure and no fee appears anywhere in the
Threads API documentation read here. That is an absence of evidence rather than a statement
of price, and Meta nowhere says this API is free.

### Webhooks

Not built, and not recommended for a first version. The `replies` field under the Moderate
topic delivers "Replies on a Threads Media owned by the Threads install user" and needs
`threads_basic` and `threads_read_replies`
(<https://developers.facebook.com/docs/threads/webhooks>). Subscription happens under Use
Cases > Customize > Settings by adding the Threads Webhooks sub-use case, selecting the topic
and setting a callback URL and token. Against polling, they cost a public HTTPS endpoint, a
certificate Meta accepts, payload verification, deduplication, and the private-account rule
above, which is a silent failure rather than an error.

## What the terms say

`docs/platform-policy.md` maps this project's approval design to the clauses it exists for,
including Meta's Developer Policy 1.7, and is not repeated here. Three Threads-specific
findings are.

### The Developer Policies do not mention Threads

The Meta Developer Policies (<https://developers.facebook.com/devpolicy/>, read 2026-08-01)
carry **no last-updated date anywhere in the page**. Any date you see attached to them
elsewhere, including in the research behind this file, belongs to a different document.

The word "Threads" does not appear in the policies at all. Section 5 is titled "Messenger
Platform and Instagram Messaging APIs", section 6 is Instagram Platform, section 11 is Pages
API, and there is no Threads section. The rules that govern a Threads app are therefore the
general ones in sections 1 and 2, with no product-specific carve-out to fall back on in
either direction. Clauses 1.4 ("Don't confuse, deceive, defraud, mislead, spam or surprise
anyone") and 1.7 ("Obtain consent from people before publishing content or taking any other
action on their behalf") are the ones a reply tool is measured against.

The messaging clauses in section 5 that forbid unsolicited automated messages are scoped by
that section's own title to Messenger and Instagram Messaging. Citing them at Threads, in
either direction, is citing the wrong document.

### The Threads Terms of Use, and the clause about commercial use

The Threads Terms of Use are readable at <https://help.instagram.com/769983657850450>, Last
Updated **28 May 2025**. The `terms.threads.com` host that secondary sources cite fails DNS
resolution.

> "3. How You Can't Use the Threads Service
>
> a. You agree that you shall not ... (i) exploit the Threads Service for any commercial
> purpose; (ii) introduce any viruses ...; (iii) circumvent ... any technological measure
> ...; and (iv) use any robot, spider, crawlers, scraper or other automatic device, process,
> software or queries that intercepts, 'mines', scrapes, extracts or otherwise accesses the
> Threads Service to monitor, extract, copy or collect information or data from the Threads
> Service, or engage in any manual process to do the same."

Clause (iv) is the one everybody quotes. Clause (i) is the one that matters to anybody using
a Threads account to sell something, and it is the first item in the list.

Our reading, stated as a reading rather than as advice: these are the consumer terms for
using the Threads service as a person, and API access is granted under a separate set of
documents (the Meta Platform Terms and the Developer Policies) through an app that Meta
itself reviews and approves for named business purposes. An App Review submission describes
a commercial use case and is approved on that basis. Reading (i) as prohibiting the API
Meta operates for businesses would prohibit the product Meta sells access to.

That argument is ours and it is not Meta's. Nothing in the Threads Terms carves out API
access from (i), and no page read here states that the developer documents supersede the
consumer terms for a business account. An operator selling something through replies drafted
by this tool should get their own advice rather than this paragraph's.

Section 3(b) closes the loop: "you agree that the Instagram Terms of Use, including the
section titled 'Your Commitments' also applies to your use of the Threads Service." Those
terms (<https://help.instagram.com/581066165581870/>, effective 1 January 2025) prohibit
collecting information "in an automated way ... without our express permission". A properly
reviewed app holding a user-granted token has that permission by construction, which is the
same reading `docs/platform-policy.md` already applies to the equivalent Instagram clause.

### The clause that does not exist

Several secondary sources quote the Threads Terms as prohibiting "any form of auto-responder
or spam" and "any processes that run or are activated while you are not using Threads". Both
documents above were read end to end. Neither phrase appears in either. It is legacy
Instagram terms language from before 2013, and it is quoted often enough that somebody will
raise it at you. It is not in the current terms.

No clause requiring disclosure of software-assisted reply text was found in the Developer
Policies, the Threads Terms or the incorporated Instagram Terms. Absence of a found clause is
not proof of absence, and the EU AI Act obligation documented in `docs/platform-policy.md` is
a law rather than a Meta policy and applies here as it applies everywhere else.

## What is still unknown

Every item here failed to resolve against a primary source, or cannot resolve without a live
call.

**Whether pending replies are excluded from `/replies` and `/conversation`.** "Replies to
these posts must be approved to get published and are hidden until then" is the closest
sentence, and it does not name those two endpoints. One post with `enable_reply_approvals`
on, one reply from another account, and one `GET` settles it.

**Whether `reply_to_id` takes a reply id or only a container id.** Meta's parameter
description says container. The operation it is documented under is answering a reply. Two
calls settle it, and nobody has made them.

**Whether a professional account is required.** Instagram states its professional-account
requirement repeatedly. No Threads developer page read here states an account-type
prerequisite either way, and every Threads account is tied to an Instagram identity, so the
question is real rather than pedantic.

**What invalidates a token besides expiry.** Password change, scope revocation, review
status change and account deletion are all undocumented for Threads. The `debug_token`
endpoint reports the outcome and no page reports the causes.

**Whether hiding a reply removes it from `/replies` and `/conversation`.** The
reply-management and retrieve-replies pages were both read with this question in hand and
neither addresses it.

**Whether the Threads use case can share an app with Facebook Login.** A search summary
asserts the two are incompatible in one app and that Threads is compatible with the Page use
case. The create-an-app pages behind that claim returned 404 through every retrieval
attempted, so it is unconfirmed in both directions. What is confirmed is only that the
Threads app id and secret are a separate pair from the app's other pair.

**How long Business Verification takes, and what documents it accepts.** Not established.
The verification page states the requirement and the dashboard path and defers the document
list elsewhere. Whether a sole trader without a registered company can verify at all is
unknown. This matters only for the reviewed path, not for the single-operator path.

**Whether App Review's published turnaround is current.** The primary page says less than a
week, often 2-3 days. A third-party blog claims the figure doubled during 2026. No
Meta-authored page confirms or denies the slower number, and the published figure covers one
pass rather than a submission that gets rejected and resubmitted.

**Whether `/conversation` returns `replied_to` and `root_post`.** Those fields are published
for the replies endpoints. The conversation page does not repeat the field list, and a tool
that identifies nested replies depends on them being there.

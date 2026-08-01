# TikTok

Reading the comments on videos an operator's own TikTok account posted, and publishing
one approved reply at a time. None of it is wired up. Read the first section before you
read anything else here.

TikTok API for Business, Accounts API `v1.3`. Every page cited below was read on
**2026-08-01**, first by a research pass and then by a separate adversarial pass that
re-rendered most of the same pages and corrected seven claims. Where the two disagreed,
the second one is what is printed here. Where only the first one reached a page, the
sentence quoting it says so.

## There is no TikTok connector, and the API everyone says does not exist

**commentdraft ships one connector and it is Facebook.** There is no TikTok connector,
no TikTok credential handling and no TikTok code anywhere in this package. Writing
`platform = "tiktok"` into `[source]` or `[publish]` is refused before a credential is
asked for, with the line `unknown platform: tiktok. registered: facebook`. This page is
the specification a connector would be built against, and the account of what it takes
to be allowed to run one.

What makes it worth writing down is that the API exists.

**"TikTok has no comment API" is the wrong answer, repeated everywhere.** It is true of
`developers.tiktok.com`, which is the portal every tutorial and every blog post means.
Login Kit, the Display API and the Content Posting API have no way to read or reply to a
comment, and TikTok's whole webhook catalogue on that portal is four events, none of
them about comments (<https://developers.tiktok.com/doc/webhooks-events>).

It is false of `business-api.tiktok.com`, a separate product line under separate
onboarding, whose Accounts API has exactly the two endpoints this tool needs:

```
GET  https://business-api.tiktok.com/open_api/v1.3/business/comment/list/
POST https://business-api.tiktok.com/open_api/v1.3/business/comment/reply/create/
```

Both are documented, both are current, and neither is mentioned by the articles that
conclude the feature is missing. TikTok's own product taxonomy names the split:

> "TikTok's Accounts API is a series of three interface services provided by the API for
> Business team to developers. Through integrating and calling the Accounts API,
> developers can leverage our interface to interact with TikTok Business Account and
> TikTok Personal Accounts, including pulling Reporting / Insights, Comment Moderation,
> and Video Publishing for a Business Account or Personal Account."
>
> <https://business-api.tiktok.com/portal/docs?id=1737944384433218>

Comment moderation is named there, and named again on the same page under Authorized
Uses, which is the list a reviewer applies:

> "Manage the organic presence of brands or creators' owned accounts on TikTok,
> including: Publishing video or photo posts. Moderating comments. Analyzing TikTok
> profile and post insights. Performing ad authorization for TikTok posts."

### Who TikTok will register as a developer

TikTok will not onboard a solo individual as the developer of record. The company
requirement is stated on the developer registration page in TikTok's own words:

> "Fill in your company website. Your website should: ... Be a company website, rather
> than a personal website. Currently, we are unable to onboard personal accounts or
> individual developers. If you are part of a company, please use your company website."
>
> "Note that communication email must be a verified company domain email. You will be
> rejected if you are using a personal email or a temporary email."
>
> <https://business-api.tiktok.com/portal/docs?id=1738855176671234>

That gate lands on whoever registers as the developer. It does not land on the TikTok
account whose comments are being read, which may be a Business Account or a Personal
Account. See [If you cannot qualify](#if-you-cannot-qualify) for what that separation
makes possible.

On top of the two reviews that were already there, a third gate was added in March:

> "Note: To ensure proper use of the Accounts API, starting March 20, 2026 at 00:00
> (GMT+0), developers must complete the Accounts API Access Application Form before
> submitting a new developer app or requesting a scope increase that includes the
> 'TikTok Accounts' permission scope."
>
> <https://business-api.tiktok.com/portal/docs?id=1737944384433218>

No turnaround is published for that form. The published figures cover the other two
reviews only, so they are the floor rather than the total.

| Cost | Where it lands |
|---|---|
| The developer of record must be a company with a matching domain and a real website | A solo consultant cannot register at all. Nothing downstream matters until this resolves |
| Two reviews before a first call | Developer profile: "three business days". App: "The review may take 2 to 3 business days" |
| A third gate since 2026-03-20 | The Accounts API Access Application Form, with no published turnaround |
| Selecting the "TikTok Accounts" permission grants everything beneath it | There is no read-only posture that way. See [Which permission you ask for](#which-permission-you-ask-for) |
| Access tokens last 24 hours | Something has to hold a refresh loop, which a command line tool run in bursts does not naturally have |
| Every app starts at the Basic rate limit level | Increases are a manual application, one level at a time |

Compare that with `docs/platforms/facebook.md`, where an operator who owns the Page and
creates their own app faces no review of any kind.

## What is verified here, and what is not

**Nobody has made any of these calls.** No TikTok credential has ever been in this
project, no request has ever been sent to `business-api.tiktok.com`, and there is no
code here to send one. Every figure, path and parameter below is documentation, read
twice.

Verified against TikTok's live documentation, read 2026-08-01 by both passes:

| What | How far the check went |
|---|---|
| The two comment endpoints, their methods and headers | Rendered, parameter by parameter, including bounds and defaults |
| The read and write scope split | Rendered, in prose and in TikTok's own permission-to-endpoint table |
| `redirect_uri` on the token exchange | Rendered on the Authentication page, where it is marked Required |
| The `comment.update` payload and its full `comment_action` enum | Rendered, with a worked example payload |
| Rate limit levels and the throttle error code | Rendered on two pages, the specific one and the general one |
| Quoted policy text | Quoted verbatim from the page named beside it |

Read by the research pass and **not re-rendered** by the verifier, so carrying one
reader's word rather than two:

- The registration and app-creation pages: the company gate quoted above, the "three
  business days" and "2 to 3 business days" review figures, and the cap of five
  developer apps per developer (`?id=1738855176671234`, `?id=1738855242728450`).
- The authorization page: the 512x512 app logo requirement, the redirect URL format
  rules, the ten-registered-one-active behaviour, and `&disable_auto_auth=1`
  (`?id=1738083939371009`).

The company gate is the single most consequential sentence on this page and it is in
that second list. It is quoted verbatim from a rendered page, by one reader, once. Check
it yourself before you make a decision on it.

Not resolvable from documentation at all, and listed in full under
[What is still unknown](#what-is-still-unknown): whether the 1,200 character reply limit
counts code points or bytes, what the Access Application Form asks for, what its
turnaround is, whether any of this costs money, and what invalidates a token outside its
stated expiry.

## The five surfaces, and which one has comments

Confusing these is the expensive mistake, because four of them are on the portal with
the better search ranking and the fifth is the only one that works.

| Surface | Domain | Read comments | Reply to comments | Who can use it |
|---|---|---|---|---|
| Display API | `developers.tiktok.com` | No | No | Any registered developer |
| Content Posting API | `developers.tiktok.com` | No | No | Any registered developer |
| Research API | `developers.tiktok.com` | Any public video, not scoped to owned | No | Vetted academic and non-profit researchers, explicitly not commercial users |
| Marketing API comments | `business-api.tiktok.com` | Ads only | Ads only, `ad_id` required | TikTok Ads Manager advertisers |
| **Accounts API comments** | `business-api.tiktok.com` | **Yes, on an owned account's videos** | **Yes** | Companies approved for the "TikTok Accounts" permission |

The Display API's own overview lists its entire surface, and there is nothing
comment-shaped in it:

> "Display API has three major APIs: `/v2/user/info/`, `/v2/video/list/`, and
> `/v2/video/query/`."
>
> <https://developers.tiktok.com/doc/display-api-overview>

The Content Posting API's only comment-adjacent feature is a publish-time toggle,
`disable_comment` in the request body, returned as `comment_disabled` from Query Creator
Info (<https://developers.tiktok.com/doc/content-posting-api-get-started>). It turns
comments on or off for a video you post and reads nothing.

The Research API is the one people find and then discover they cannot have. It does have
a comments endpoint, `POST https://open.tiktokapis.com/v2/research/video/comment/list/`,
gated on the `research.data.basic` scope, with a quota of 1,000 requests and 100,000
records per day at 100 records per request, reset at 12 AM UTC
(<https://developers.tiktok.com/doc/research-api-specs-query-video-comments>,
<https://developers.tiktok.com/doc/research-api-faq>). It is read-only, and TikTok
answers the eligibility question on its own FAQ page in one word:

> "I am a creator, advertiser, or commercial user. Am I eligible for access to the
> Research Tools? No."
>
> <https://developers.tiktok.com/doc/research-api-faq>

### TikTok's own documentation site will serve you the wrong page

`business-api.tiktok.com` is a client-side application that returns an empty shell to
`curl`. That much is ordinary. The part that costs time is that a friendly slug URL such
as `/portal/docs/permission-scope/v1.3` does not 404 when it fails to resolve. It
silently renders a generic landing page (`doc_id=1797738007505921`), which looks like a
page rather than like an error. Two different slugs were fetched and diffed to
byte-identical output, so this is reproducible rather than a one-off.

Use the numeric form, `/portal/docs?id=<doc_id>`, which is what every citation on this
page uses. To map titles to ids for pages not cited here, capture the response of
`GET /gateway/api/doc/client/platform/tree/get/?language=ENGLISH&identify_key=...`,
which the application calls on load and which returns the whole documentation tree as
nested `{title, doc_id, child_docs}`.

Some doc pages also return `{"code":40303,"msg":"The current user is not a developer so
cannot use this function."}` when queried without a logged-in session, so a page that
reads as missing may only be gated.

## What it takes to qualify

Six steps, in order, with the published figures next to the two that have any.

1. **Create a TikTok For Business account.** Email or phone, terms, a verification code.
   No company gate at this step, which is what makes the next one a surprise.
   (<https://business-api.tiktok.com/portal/docs?id=1738855099573250>)

2. **Register as a developer.** This is the gate. You supply a communication email on a
   verified company domain, a company website that is not a personal site, a company
   name matching that domain or website, a user type (Technology Company, Direct
   Advertiser, or Agency), and a prose description of your intended use of TikTok data
   and the API. The two sentences that decide whether you can proceed at all are quoted
   in [Who TikTok will register as a developer](#who-tiktok-will-register-as-a-developer).

   Published figure: "You will be notified of the review result in three business days."
   (<https://business-api.tiktok.com/portal/docs?id=1738855176671234>)

3. **Complete the Accounts API Access Application Form.** Mandatory since 2026-03-20 for
   any new app or scope increase touching "TikTok Accounts". The form is at
   <https://bytedance.sg.larkoffice.com/share/base/form/shrlgu4WEvtSXpEDLcCw56u4Rfc> and
   is login-gated, so its fields and its turnaround are both unknown here. Neither pass
   could open it.

4. **Create a developer app.** Name, a description of intended use, whether access is
   internal-only or shared, a redirect URL, and the permissions you want. Read
   [Which permission you ask for](#which-permission-you-ask-for) before you pick, because
   the obvious choice on this screen is the one that grants the most.

   Published figure: "The review may take 2 to 3 business days." A developer may hold up
   to five apps. (<https://business-api.tiktok.com/portal/docs?id=1738855242728450>)

5. **Upload an app logo before you share the authorization URL.** JPG, JPEG or PNG, no
   larger than 512x512. Without it the account holder who opens your authorization link
   sees an error page instead of the consent screen, which reads as your link being
   broken.

6. **Have the TikTok account holder authorize the app.** You send them the authorization
   URL from My Apps, App Detail, Basic Information. It is a standard
   `https://www.tiktok.com/v2/auth/authorize?{parameters}` consent screen. They approve,
   and you receive an `auth_code` that is valid for ten minutes and can be used once.
   (<https://business-api.tiktok.com/portal/docs?id=1738083939371009>)

A sandbox account is available before any of this is pointed at a real account. TikTok's
Get Started page lists it as one line under Sandbox accounts:

> "To test your integration without impacting your real TikTok For Business account, see
> here."
>
> <https://business-api.tiktok.com/portal/docs?id=1735713609895937>

The floor, adding only the figures TikTok publishes, is five to six business days. The
form in step 3 sits between steps 2 and 4 with no published number attached, so the real
total is unknown and cannot be estimated from anything TikTok has said.

## If you cannot qualify

Most readers of this page will not qualify. These are the routes that remain, in the
order worth trying.

**Use the connector that ships.** commentdraft's Facebook connector needs no App Review
and no Business Verification for an operator who owns the Page and creates their own
app. `docs/platforms/facebook.md` is the whole path, and it is the shortest one this
project has found. If the same audience exists on both, that is a working loop today
against nothing but a token you issue yourself.

**Separate the developer from the account.** The company requirement applies to the
developer of record, not to the TikTok account being moderated, and the Accounts API
supports Personal Accounts as well as Business Accounts. A creator with a personal
TikTok account can be moderated by an app registered by a company they work with or for,
because the account holder authorizes the app rather than owning it. If a company is in
the picture anywhere, that company registers and the creator authorizes. That is the
route that turns a refusal into an approval, and it costs one conversation.

**Draft in commentdraft and post by hand.** Two of the four commands never touch any
platform:

```bash
commentdraft run --config config.toml --comments comments.csv --out out
commentdraft review out/review.csv --out out
```

`run` calls your model gateway and writes `out/review.csv`. `review` renders
`out/review.html` with a draft banner on it until a person passes `--approved`. Neither
one needs a connector or a `[publish]` table. What they need is a comments CSV,
and `docs/comments-csv.md` documents every column so you can build one from whatever you
can export or copy. The reply then goes into the TikTok app by hand. That loses the
audit file and the id read-back, and it keeps the part that is actually the work.

`commentdraft chat --config config.toml` does the same thing one comment at a time, if
you want to see decisions and traces before you build a CSV at all.

**What does not work, so you do not spend a week on it.** The Research API is closed to
commercial users by its own FAQ and cannot reply to anything. The Marketing API's comment
endpoints require an `ad_id` and reach ad comments only. The Display and Content Posting
APIs have no comment surface. Scraping the web interface is what the Community Guidelines
clause in [Policy](#policy-on-automation) is written about, and it puts the account at
risk rather than the app.

## Which permission you ask for

The Accounts API is the surface with the largest gap between what you need and what the
obvious selection grants.

TikTok publishes a three-level permission hierarchy mapped to concrete endpoints
(<https://business-api.tiktok.com/portal/docs?id=1753986142651394>):

| Level | ID | Name | Endpoints |
|---|---|---|---|
| 1st | `18000000` | TikTok Accounts | / |
| 2nd | `18030000` | Business Comment | / |
| 3rd | `18030100` | Get Business Comment | `/business/comment/list/`, `/business/comment/reply/list/` |
| 3rd | `18030200` | Manage Business Comment | `/business/comment/create/`, `/business/comment/delete/`, `/business/comment/hide/`, `/business/comment/reply/create/`, `/business/comment/like/` |

The read and write split is documented, on that page, with the endpoint lists attached.
Anyone who tells you it has to be inferred from the scope names has not found this table.

What the same page says about the levels is the part that decides your posture:

> "TikTok API for Business permissions consist of three levels... If an access token
> grants you a first-level permission, then you can access all the endpoints related to
> the second-level and third-level permissions under the first-level permission with the
> access token."

"TikTok Accounts" is the **first-level** permission. Selecting it grants Get and Manage
Business Comment together, plus Business User, Business Media and Business Content, which
includes video publishing. **There is no read-only posture available by selecting "TikTok
Accounts".** An app that wants to read comments and nothing else has to request the
third-level permission, `18030100`, specifically.

That matters here more than it would elsewhere. The posture this project recommends for
every platform is to read for a while before asking anyone for a write scope, and on
TikTok the default selection destroys that posture in one click.

The Accounts API token exchange returns string scopes rather than these numeric ids. A
real, redacted scope list from the token endpoint contains both comment scopes:

```
...,user.info.basic,comment.list,biz.brand.insights,...,comment.list.manage,video.upload,...
```

TikTok glosses the read one in prose on the webhook event page:

> "To ensure that you can receive `comment.update` events, the TikTok account owner needs
> to authorize the developer app with the `comment.list` scope (Read the comments and
> replies of your in-app content)."
>
> <https://business-api.tiktok.com/portal/docs?id=1810515104773122>

The two naming systems coexist. The numeric ids key the Marketing API's
`/oauth2/access_token/` flow and the string scopes come back from the Accounts API's
`/tt_user/oauth2/token/` flow, and TikTok never prints them side by side. Read back what
you were actually granted with `POST /open_api/v1.3/tt_user/token_info/get/` rather than
assuming the mapping.

## Getting a token

The Authentication reference for all of this is
<https://business-api.tiktok.com/portal/docs?id=1738084387220481>.

1. Receive the `auth_code` on your redirect URL after the account holder consents. It is
   valid for ten minutes and can be used once, so the exchange has to fire on the
   redirect rather than after a copy and paste.

2. Exchange it:

   ```
   POST https://business-api.tiktok.com/open_api/v1.3/tt_user/oauth2/token/
     client_id
     client_secret
     auth_code
     grant_type
     redirect_uri
   ```

   **`redirect_uri` is required and is the parameter most write-ups leave out.** TikTok
   states why on the same page:

   > "The endpoints require `redirect_uri` for better security"
   >
   > "Its value must be the same as the TikTok account holder redirect URL set in the
   > app."

   An implementation that omits it fails at the first call, before anything else on this
   page can be tested.

3. Keep three things out of the response. The access token, `expires_in: 86400`, which
   is 24 hours. The refresh token, `refresh_token_expires_in: 31536000`, which is one
   year. And `open_id`, which is the value every subsequent Accounts API call sends as
   `business_id`.

4. Refresh at `POST /open_api/v1.3/tt_user/oauth2/refresh_token/` with `client_id`,
   `client_secret`, `grant_type` and `refresh_token`. Refresh does **not** take
   `redirect_uri`. Renewal returns a fresh access and refresh token pair, so whatever
   stores them has to store both.

5. Revoke at `POST /open_api/v1.3/tt_user/oauth2/revoke/` with `client_id`,
   `client_secret` and `access_token`. The account holder can revoke independently from
   inside the TikTok app: Settings and privacy, Security, Manage app permissions, the
   app, Remove access. Neither side has priority over the other.

Every call afterwards carries the header `Access-Token: {access-token}`.

Redirect URL rules, from the authorization page and read by one pass only: absolute
HTTPS, ending in `/`, no query parameters, no ports, no anchors, between 10 and 512
characters. Up to ten may be registered per app and exactly one is active at a time.
Adding a new one does not make it active.

A 24 hour access token is the shape of this connection that a command line tool has to
answer for. commentdraft is used in bursts, and `docs/platforms/facebook.md` describes a
Page token with no expiry at all. A TikTok connector cannot hold a working credential in
an environment variable the way the Facebook one does: anything more than a day old is
dead, so either the operator re-authorizes before every session or the connector owns a
refresh path and a place to write the rotated pair. Neither exists here.

## Reading comments

```
GET https://business-api.tiktok.com/open_api/v1.3/business/comment/list/
```

Header `Access-Token`. Required parameters are `business_id`, which is the `open_id`
from the token exchange, and `video_id`, which is an owned video's `item_id` from
`/business/video/list/`.

| Parameter | Values | Default |
|---|---|---|
| `comment_ids` | filter, maximum 30 | none |
| `include_replies` | boolean; true returns up to 3 replies inline per top-level comment | false |
| `status` | `PUBLIC` or `ALL` | `ALL` |
| `sort_field` | `likes`, `replies`, `create_time` | unset, see below |
| `sort_order` | `asc`, `desc`, `smart` | |
| `cursor` | | 0 |
| `max_count` | 1 to 30 | 20 |

<https://business-api.tiktok.com/portal/docs?id=1760232109619202>

What the endpoint covers, in TikTok's words:

> "Use this endpoint to access all the comments or only the specified comments (along
> with related information) - both public and hidden - that have been created against a
> specific organic video posted by an owned TikTok Account."

Four behaviours to build around rather than discover.

**Sorting is random by default.** If `sort_field` is unset, order is not stable, which
makes a cursor walk over an unsorted result the wrong way to enumerate anything.

**`max_count` is a ceiling and not a promise.**

> "Due to our trust and safety policies, it is possible that the endpoint returns less
> than the `max_count` number of comments even if `has_more` is true."

A short page is not the end of the data.

**Past 500 comments on one video, results may repeat.**

> "Note: If the number of comments on the owned video exceeds 500, the first 500 comments
> will be returned according to the specified sorting, and the remaining comments will be
> returned in reverse order based on the number of likes. Also, the comments beyond the
> first 500 and the first 500 comments themselves are not deduplicated and may contain
> duplicates."

Anything reading a busy video has to deduplicate on `comment_id` itself. commentdraft's
`--state` file already does exactly that for Facebook, keyed on the id the platform hands
over, and `docs/limits.md` describes what it can and cannot promise.

**Hidden is four different things wearing one status.**

> "Hidden comments returned by the endpoint can include those hidden by the video owner,
> and comments hidden due to moderation actions, user privacy settings, or other
> system-level filters."

The API returns all four as hidden and offers no field distinguishing them. A reply to a
comment hidden for privacy reasons may not be visible to the person who wrote it.

Replies to a comment come from a companion endpoint,
`GET /open_api/v1.3/business/comment/reply/list/`
(<https://business-api.tiktok.com/portal/docs?id=1762228430145538>).

## Publishing a reply

```
POST https://business-api.tiktok.com/open_api/v1.3/business/comment/reply/create/
```

Headers `Access-Token` and `Content-Type: application/json`. Required body parameters are
`business_id`, `video_id` and `comment_id`. `text` is conditional, required unless the
reply is an image, and carries the limit "Length limit: 1,200 characters (UTF-8
encoding)."

The response returns the new `comment_id`, the `parent_comment_id` it replied to,
`video_id`, `create_time` and the `text` it echoes back. `user_id` is marked
to-be-deprecated in favour of `unique_identifier`, so nothing new should read it.

<https://business-api.tiktok.com/portal/docs?id=1762228448779266>

### The endpoint reaches further than an owned account

The first sentence of the endpoint page:

> "Use this endpoint to create a reply to an existing comment on an organic video posted
> by an owned TikTok Account or others' TikTok Account."

That second clause is the whole surface, and most descriptions of this API drop it. An
approved app can reply to comments under videos it does not own, which is the shape of
API-driven promotional spam and a materially wider exposure than moderating your own
audience.

commentdraft rules it out by design rather than by permission. `commentdraft pull` reads
the account's own posts and the comments on them, a reply is addressed to the id of the
comment it answers, and there is no path in this tool that starts from someone else's
video. `docs/platforms/facebook.md` makes the same choice on the Facebook side by reading
`published_posts` rather than `/feed`. A TikTok connector must make it explicitly, in the
connector, because the platform will not make it for you.

### No batch primitive, which is the one thing that helps

The Comments group is exactly eight endpoints: get comments, get replies, create,
upload comment image, reply, like and unlike, hide and unhide, delete
(<https://business-api.tiktok.com/portal/docs?id=1776065099288577>). Every one of them
acts on a single comment. There is nothing to send a hundred replies with, which lines
up with a design where a person approves one reply per keystroke.

### The spam trap

TikTok's own warning, on the reply endpoint page:

> "To prevent comments from being flagged as spam and subsequently hidden by the system,
> avoid posting a high volume of comments with largely similar content within a short
> timeframe. If a comment is flagged as spam, you will not receive the `comment.update`
> webhook event with `comment_action` set to `set_to_public`."

Read that alongside `docs/limits.md`. A model grounded in one source document produces
near-identical replies to near-identical questions, which is the exact input this
sentence describes. Nothing in the drafting step can prevent it while a draft is being
written; the run report is where it surfaces afterwards.

The failure is not fully silent, which the [webhook](#the-comment-update-webhook)
section explains: `set_to_hidden` is an observable state. What is silent is treating the
absence of `set_to_public` as a timeout rather than as a verdict.

Image replies are a separate path. `reply_image_url` requires the URL's domain to be
pre-verified as a URL property; the `image_uri` path does not. A text-only tool skips the
whole Manage URL properties step in the onboarding sequence, which is a real shortening
of the path the full documentation implies.

## The comment update webhook

Subscribe with `POST /open_api/v1.3/business/webhook/update/`, `event_type` set to
`COMMENT`. The callback URL must be HTTPS and must return HTTP 200 immediately. Failed
deliveries are retried with exponential backoff for up to 72 hours and then discarded,
and delivery is at-least-once, so a handler has to be idempotent
(<https://business-api.tiktok.com/portal/docs?id=1759977800177665>).

The coverage sentence is broader than a reader would guess, and the last clause is the
one that decides whether any of this is useful:

> "Fired within five minutes of a comment or reply being created, deleted, or the comment
> visibility settings being modified on any photo post or public video post under an
> owned TikTok account. This applies to both posts published through
> `/business/video/publish/` or `/business/photo/publish/` and posts manually published
> through the TikTok App."
>
> <https://business-api.tiktok.com/portal/docs?id=1810515104773122>

An operator who posts from their phone is covered. A reading that limited this to videos
published through the API would have made the whole thing useless for almost everyone.

Payload fields: `comment_id`, `video_id`, `parent_comment_id`, `comment_type`
(`comment` or `reply`), `comment_action`, `timestamp`, `unique_identifier`, `text`.

| `comment_action` | Meaning |
|---|---|
| `insert` | created |
| `delete` | deleted |
| `set_to_hidden` | hidden by the user or through moderation |
| `set_to_friends_only` | restricted to the user's friends |
| `set_to_public` | restored to publicly visible |

`set_to_friends_only` is a visibility mode with no Facebook equivalent and it changes
what a reply means: a reply to such a comment may be invisible to everyone except the
commenter's friends.

commentdraft polls and does not consume webhooks on any platform. The reason is the same
one `docs/platforms/facebook.md` gives: a public HTTPS endpoint with a certificate the
platform accepts, plus deduplication the platform makes your problem, is a larger thing
to own than a command a person runs. A TikTok connector would still want a periodic read
back through `comment/list` rather than trusting webhook silence, for the reason in the
spam section above.

## Where this would sit in commentdraft

`commentdraft pull`, `run`, `review` and `publish` are real commands and two of them
touch a platform. A TikTok connector would register under the name `tiktok` and answer
the same two calls every connector answers, `fetch_comments` and `publish_reply`, and the
config would name it in `[source]` and `[publish]` the way `docs/configuration.md`
documents. **None of that exists.** The name is unregistered, so both tables refuse it
before a credential is read.

Four decisions a connector author would have to make that Facebook did not force:

The credential rotates. A 24 hour access token means either the operator re-authorizes
every session or the connector owns the refresh call and a place to write the rotated
pair, which is a shape `credential_env` alone does not express.

`--since` has no server-side equivalent worth using. `comment/list` sorts randomly
without `sort_field`, its page size is not guaranteed, and its own results are not
deduplicated past 500. Filtering on our side after the fetch, which is what the Facebook
connector does, is the answer here for stronger reasons than it was there.

The write check has less to prove and something new to prove. TikTok returns
`parent_comment_id` on the reply response directly, so the read-back that Facebook needs
in order to rule out an overwrite has an easier job. What replaces it is confirming the
reply is actually visible, because a spam-throttled reply returns normally and then does
not appear.

`video_id` has to come from somewhere. `comment/list` is per video, not per account, so a
pull enumerates `/business/video/list/` first and then walks it. The Facebook connector
has the same shape with `published_posts`.

## Limits

`docs/limits.md` covers what commentdraft cannot do regardless of platform. This section
is what TikTok imposes.

### Rate limits

Two ceilings apply at once
(<https://business-api.tiktok.com/portal/docs?id=1738084416214017>):

> "The rate limit per authorized TikTok account and Accounts API endpoint is 40 queries
> per minute (QPM). Additionally, there is a separate rate limit for all Accounts API
> endpoints combined, which is determined by the global rate limit level assigned to your
> developer application."

| Global rate limit level | QPM across all Accounts API endpoints |
|---|---|
| Basic | 600 |
| Advanced | 1,000 |
| Premium | 1,000 |
| Ultimate | 1,000 |

What sets that level is on the general rate limits page rather than the Accounts API one
(<https://business-api.tiktok.com/portal/docs?id=1740029171730433>):

> "All apps are set to Basic level by default. To change your QPS limit, please apply
> through My Apps > App Detail > Authorization."
>
> "We can only increase API rate limiting one level at a time (from Basic to Advanced /
> from Advanced to Premium / from Premium to Ultimate). When applying, provide the reason
> for API rate limit increase."

So a new app starts at 600 QPM combined and there is no automatic path off it. Moving up
is another written application, and reaching Ultimate is three of them.

A throttled call returns `"code": 40100`. A QPM breach clears after a five minute wait. A
QPD breach clears at 00:00 UTC. Same page.

At 40 QPM per account per endpoint, the ceiling is not what a review loop with a human in
it will meet first.

### Replies per day

**Unpublished.** No per-day ceiling on comments or replies appears anywhere in the
Accounts API documentation. The only quantified limits are the two QPM figures above,
which count calls per minute. The behavioural ceiling is the spam detection quoted in
[The spam trap](#the-spam-trap), enforced without a published threshold for either "high
volume" or "largely similar".

### Cost

**Unpublished for this product.** There is no pricing page for TikTok API for Business
and no metering documentation. The only statement in either direction governs the other
portal:

> "TikTok does not currently charge for use of the TikTok Developer Services; however,
> TikTok reserves the right to do so in the future, at its sole discretion."
>
> <https://www.tiktok.com/legal/page/global/tik-tok-developer-terms-of-service/en>, section V

That covers `developers.tiktok.com`. No equivalent sentence was found for
`business-api.tiktok.com`. Absence of a price is not a promise of one.

### Insights latency

Not comments, and easy to conflate with them. Profile and post insights carry a 24 to 48
hour latency and only become available after the account owner turns Analytics on
manually in the TikTok mobile app
(<https://business-api.tiktok.com/portal/docs?id=1740304387032066>). Any surface showing
numbers beside a comment is showing yesterday's numbers.

## What breaks, and what each failure means

### The consent screen that never appears

Two separate causes, neither of which produces a useful error.

No app logo uploaded, or one larger than 512x512, and the account holder opening your
authorization URL gets an error page rather than the consent screen. It reads as a broken
link.

On a re-authorization for permissions already granted, TikTok skips the consent screen by
default. Append `&disable_auto_auth=1` to force it back, which is what you need when
rehearsing the flow or when checking that a newly added scope is really being asked for.

### `auth_code` burned before it was used

Ten minutes, one use. A manual copy and paste between a browser and a terminal is a
plausible way to lose it, and losing it means going back to the account holder for another
consent. Exchange it on the redirect.

### The redirect URL that is registered and not active

Up to ten redirect URLs may be registered per app and exactly one is active. Registering a
new one does not switch to it. An app that authorizes against an inactive URL fails at the
consent step for a reason that is not on the screen.

### A reply that succeeded and never appeared

The reply call returns normally when a comment is flagged as spam. The absence of a
`comment.update` event carrying `set_to_public` is the only signal, and absence is not
something to poll for. A `set_to_hidden` event is an observable state and is worth
handling; a reply that produces neither, and that a later `comment/list` read cannot find,
is the case that needs a person.

### Comments that arrive twice

Past 500 on one video, TikTok says the results are not deduplicated. Anything that treats
the API's output as a set will draft the same reply twice.

### The documentation link that serves a different page

Covered in [The five surfaces](#the-five-surfaces-and-which-one-has-comments). A slug URL
that fails to resolve renders a generic landing page rather than an error, so a quote you
cannot find on the page you opened may be a routing failure rather than a documentation
change. Re-open it by numeric id before concluding TikTok changed something.

## Policy on automation

`docs/platform-policy.md` maps this project's safety properties to the clauses they exist
for. This section is what TikTok specifically says.

The Accounts API's own usage policy is the most directly on point
(<https://business-api.tiktok.com/portal/docs?id=1737944384433218>):

> "Please use the Accounts API only in accordance with permitted usage as indicated below.
> TikTok reserves the right to revoke a developer's Accounts API access at any time
> without prior notice in the event of unintended use, policy violations, or misuse or
> abuse of the Accounts API."

Its Authorized Uses list names "Moderating comments" outright, quoted in full in the first
section. Its Prohibited Uses are about data extraction and content migration:

> "Extract reports of TikTok profiles and posts from authorized creators' accounts, and
> use the aggregated data to develop a self-built affiliate influencer marketing program...
> instead of using the TikTok One platform or API. Download TikTok videos and images,
> promote third-party solutions to save user data or media from TikTok, or migrate content
> to another TikTok account or other social media platforms."

The Developer Terms of Service, last modified 2025-12-26
(<https://www.tiktok.com/legal/page/global/tik-tok-developer-terms-of-service/en>), carry
the clauses that bite:

| Clause | What it says |
|---|---|
| II.1(b) | You may "use automated means in your Application to collect information from or otherwise interact with the TikTok Developer Services", but only "solely as described in the TikTok Developer Documentation" |
| III.2(c) | You must "make a complete and accurate disclosure to your End Users of the privacy practices and policies applicable to the Application" |
| III.3(c) | You will not use the services "for any commercial or unauthorized purpose, including without limitation communicating or facilitating any commercial advertisement or solicitation or spamming" |
| III.3(g) | You will not use them in a manner that "exceeds reasonable request volume, constitutes excessive or abusive usage" |
| III.3(h) | You will not "collect or attempt to collect any personal data from TikTok users for any unauthorized or unlawful purpose or build... profiles, databases, or similar records on any individual" |

III.3(c) is the one to read against any reply that points at something for sale. That is a
judgment call under this clause rather than a clear pass or a clear fail, and nothing here
decides it either way.

The Community Guidelines, Integrity and Authenticity, released 2025-08-14 and effective
2025-09-13
(<https://www.tiktok.com/safety/en/policies-and-engagement/integrity-authenticity>):

> "We strictly prohibit automation tools, scripts, or other tricks designed to bypass our
> systems. These can result in content removal, account bans, or other enforcement."

That clause is aimed at systems designed to evade TikTok's own controls. Software calling
a documented, reviewed API with a person approving each individual action is a different
thing, and this page is not entitled to tell you TikTok has said so, because it has not.

**No clause anywhere names per-action human approval as a requirement or as a safe
harbour.** Nothing in the Accounts API policy, the Developer Terms or the Community
Guidelines distinguishes software that acts on its own from software a person approves one
action at a time. The support for the second reading is structural: there is no batch
endpoint, the spam system punishes volume and repetition, and the Terms require use
"solely as described in the... Documentation". None of that is a clause, and one part of
the structural argument is weaker than it looks, because the reply endpoint does permit
replying under other people's videos. Operators in regulated sectors should take their own
advice rather than this page's.

## What is still unknown

Every item here failed to resolve against a primary source, or cannot resolve without a
call nobody has made.

**Everything, empirically.** No request has ever been sent. Every path, parameter, bound
and error code above is documentation that two readers agreed on, and documentation
disagrees with implementations for a living.

**The company gate, on a second reading.** The sentence the whole page turns on was
rendered once, by the research pass, and was not re-rendered by the verifier. It costs
one page load to re-check and it decides whether the rest of this page applies to you.

**What the Accounts API Access Application Form asks for, and how long it takes.** The
form is a login-gated Lark document. Neither pass could open it. An earlier internal note
described it as asking for the full legal business name as it appears on registration
documents, business verification, and a written justification, and that description could
not be re-confirmed from any source this time. Treat it as hearsay until somebody submits
one.

**Whether "1,200 characters (UTF-8 encoding)" counts code points or bytes.** The page does
not disambiguate. For Arabic or any other non-Latin script the difference is roughly a
factor of two, which is the difference between a reply-length check that works and one
that truncates. Measure it against a sandbox account.

**What invalidates a token outside its stated expiry.** No page addresses a password
change on the account holder's side, a change in the app's review status, or the effect of
editing scopes on already-issued tokens. Facebook publishes a table of exactly this and
TikTok publishes nothing.

**How the numeric permission ids relate to the string scopes.** `18030100` and
`comment.list` describe the same read access through two naming systems that TikTok never
prints side by side. The prose gloss on the webhook page closes the gap for `comment.list`
specifically and for nothing else. Read back what you hold with
`/tt_user/token_info/get/`.

**The onboarding page details, on a second reading.** The review figures, the five-app cap,
the 512x512 logo, the redirect URL format rules and `&disable_auto_auth=1` were all read
once. None of them changes the verdict; several of them would cost an afternoon if they
are wrong.

**Whether the server product in the documentation navigation reaches comments at all.**
TikTok lists an entry there for a hosted connection described as needing no developer
account and no developer app, which is a very different eligibility story from everything
above. It reads as a separate surface rather than a shortcut into these endpoints, and
neither pass followed it. If the company gate is what stops you, it is the one thing left
to check.

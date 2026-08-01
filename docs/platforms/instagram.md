# Instagram

Reading the comments on media an Instagram professional account published, and
publishing one approved reply at a time. What that would take, because commentdraft
cannot do it today.

Instagram Platform on Graph API `v26.0`. Every Meta page cited below was read on
**2026-08-01**. Meta stamps most of its documentation with an `Updated:` date in the
page body, and where that date changes how much weight a claim carries it is printed
next to the link.

## There is no Instagram connector

commentdraft ships one connector and it is Facebook. Nothing in this repository opens a
connection to `graph.instagram.com`, nothing calls an Instagram endpoint on
`graph.facebook.com`, no configuration key names an Instagram account, and no credential
for one is read anywhere.

```toml
[source]
platform = "instagram"
```

`commentdraft pull` over that config exits 2 with `unknown platform: instagram.
registered: facebook`, before it asks for a credential. A `[publish]` table naming it is
refused the same way. The registry lists what exists, and Instagram is not on it.

What works today is the file route. Export the comments yourself into the five columns
`docs/comments-csv.md` documents, and `commentdraft run` and `commentdraft review`
behave exactly as they do for any other origin. The `platform` column accepts the string
`instagram` and is a label on the row: it selects no code path, and
`examples/sourdough-course/comments.csv` already carries rows spelled that way. Nothing
in the tool sends the result back.

This page is for whoever decides to close that gap. It covers how access is obtained,
which of Instagram's two configurations you would be on, and every constraint found on
the way, so the size of the job is known before it starts. Every sentence below
describes Meta's documentation. None of it describes observed behaviour of code in this
repository, because there is none to describe.

## What this gets you, and what it costs

An operator who owns the Instagram professional account, creates their own Meta app, and
holds a role on that app can call both halves of the job at **Standard Access, with no
App Review and no Business Verification**. Reading comments is
`GET /{ig-media-id}/comments`. Publishing a reply is `POST /{ig-comment-id}/replies`.
Meta states the conclusion outright in a decision table on its Instagram App Review page
(Updated 2026-06-30):

| Development scenario | Login type | Access level | App Review |
|---|---|---|---|
| My app is only for a business I own or manage. | No login or Instagram Login | Standard Access | Not required |
| My app is only for a business I own or manage. | No login or Facebook Login | Standard Access | Not required |
| I am a Tech Provider and my app serves multiple businesses. | Instagram Login | Advanced Access | Required |
| I am a Tech Provider and my app serves multiple businesses. | Facebook Login | Advanced Access | Required |

<https://developers.facebook.com/docs/instagram-platform/app-review/>

The **comments webhook is the exception, and it needs Advanced Access**, which needs App
Review and Business Verification. A first version therefore polls. That single fact is
the difference between an afternoon and a review cycle, and it is stated three times
across two of Meta's own pages; see [Webhooks](#webhooks-which-you-cannot-have-yet).

What it costs is on the other side of that.

| Cost | Where it lands |
|---|---|
| The long-lived token expires 60 days after issue and has to be refreshed | A token that goes 60 days without a refresh cannot be refreshed at all. The operator walks the whole authorization flow again |
| A long-lived token cannot be refreshed until it is 24 hours old | A refresh call wired to run at startup has its precondition unmet on day one |
| The rate budget scales with how often the account's content was seen | A dormant or brand new account has close to no budget. See [Limits](#limits) |
| The comments edge returns 50 per query and cannot be filtered by timestamp | There is no "everything since T" query. Pagination and local de-duplication are yours to write |
| Three constraints on the write path come from a page Meta last updated 2021-11-09 | Four years and nine months old, and it predates the Instagram Login route entirely. See [Publishing a reply](#publishing-a-reply) |
| Only top-level comments come back by default | A naive read misses every threaded reply |

Distributing this as a product other people's accounts connect to is a different story:
that needs Advanced Access on every permission.

> "Business Verification is required to get Advanced Access."
>
> <https://developers.facebook.com/docs/graph-api/overview/access-levels>

Everything below is the single-operator path unless it says otherwise.

## What is verified here, and what is not

**No Instagram endpoint has been called from this repository or on its behalf.** There is
no connector, no credential and no captured response. Not one sentence on this page
reports observed API behaviour.

Verified against Meta's live documentation, read 2026-08-01:

| What | How far the check went |
|---|---|
| Endpoint paths, host names and HTTP methods | Read on the comment-moderation guide and on the reference page for each edge |
| Scope strings | Read on the permissions reference and on the business login page, character for character |
| The `id` versus `user_id` distinction | Read on the field table of the Instagram Login get-started page, which is where the trap is documented and nowhere else |
| Access levels and what triggers App Review | Read on the access-levels page, the Instagram Platform overview and the Instagram App Review page |
| Quoted policy text | Quoted verbatim from the page named beside it, with the date read |
| Meta's own defects | Reproduced through two independent extraction methods before being called defects |
| Page staleness | Taken from the `Updated:` stamp in each page body, quoted next to the claims that rest on it |

An adversarial pass over the research behind this page pulled the raw markdown and raw
HTML of the same URLs through a text-extraction proxy and grepped them locally, because
a summarising fetch had already been caught changing what it returned. That pass found
twelve errors. Where it and the research disagreed, the raw read is what is printed
here. Two of its findings are worth naming as method rather than as content: a markdown
extraction of one reference page silently dropped three whole sections that an HTML
extraction of the identical URL contained, and the Graph API version inside Meta's
rendered code samples differed between two fetch paths of the same URL in the same
minute. Do not conclude "absent" from one extraction mode, and do not read the version
string in a rendered sample as a staleness signal.

Not verified. These are the items that matter, and each settles with a live call rather
than another pass over the documentation:

- That `POST /{ig-comment-id}/replies` behaves as documented on media created since 2021.
  Its three limitations sit on a page Meta last updated 2021-11-09.
- Whether the `comments` webhook echoes back replies the operator's own account posts.
  Four webhook pages say nothing either way.
- Whether "Reels are not supported" still describes webhook behaviour. The sentence is
  live today; nothing in the documentation confirms or denies that it is current.
- What a real throttling response carries, as opposed to what the rate-limiting page says
  it carries.
- Whether switching a personal account to Business restricts the licensed music library,
  and whether Creator differs. See [What is still unknown](#what-is-still-unknown).
- The full list of events that invalidate a token. Meta acknowledges there are others and
  does not enumerate them.

Anything that could not be established at all is under
[What is still unknown](#what-is-still-unknown) rather than smoothed into the prose above
it.

## The two routes

Meta ships two configurations of one product. They have different host names, different
scope strings and different account prerequisites, and readers lose whole afternoons to
mixing them.

| | Instagram API with Instagram Login | Instagram API with Facebook Login for Business |
|---|---|---|
| Facebook Page required | **No** | **Yes** |
| Host | `graph.instagram.com` | `graph.facebook.com` |
| Login surface | `https://www.instagram.com/oauth/authorize` | Facebook Login for Business |
| Account type | Instagram professional, Business or Creator | Instagram professional, Business or Creator, connected to a Page |
| Token you end up holding | Instagram user access token | Facebook user access token, and a Page access token for webhooks |
| Reviewable with no user interface | No | Yes. See [The carve-out](#the-carve-out-that-inverts-the-recommendation) |

The Instagram Login route says so plainly:

> "This API setup does not require a Facebook Page to be linked to the Instagram
> professional account."
>
> <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/>

The Facebook Login route says the opposite:

> "If your app implements Facebook Login for Business, your app users' Instagram
> professional accounts must be connected to a Facebook Page."
>
> <https://developers.facebook.com/docs/instagram-platform/overview/>

### The scope strings, exactly

Both families are current. The prefix is what tells them apart, and copying the wrong
family into an authorization URL produces a login screen that grants nothing useful.

Instagram Login, from
<https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login>:

```
instagram_business_basic
instagram_business_manage_comments
```

Those two are the whole set for reading comments and posting replies.
`instagram_business_content_publish` and `instagram_business_manage_messages` exist on
the same page and are not needed here.

Facebook Login, from <https://developers.facebook.com/docs/instagram-platform/overview/>
and the dependency rows on <https://developers.facebook.com/docs/permissions>:

```
instagram_basic
instagram_manage_comments
pages_show_list
pages_read_engagement
pages_read_user_content
```

`pages_read_user_content` is the one most scope lists omit, this project's own research
included. It is a documented dependency of `instagram_basic`, alongside
`pages_show_list`, and a submission that leaves it out is a submission built on a
permission whose dependency is unmet. Add `pages_manage_metadata` on top of all five if
you ever subscribe a Page to webhooks; it appears in none of the comment-moderation
permission lists.

One more permission appears conditionally on the Facebook Login route and is invisible
until it fails: `ads_management` or `ads_read` becomes required when the app user's Page
role was granted through Business Manager rather than directly on the Page. Same person,
same Page, different permission set depending on how somebody assigned the role.

**Dead scope names.** The Instagram Login scopes originally shipped with no
`instagram_` prefix: `business_basic`, `business_content_publish`,
`business_manage_comments`, `business_manage_messages`. They were deprecated on
**2025-01-27**, and Meta's own wording on what happens if you keep using them is
"Failure to do so will result in your app being unable to call the Instagram endpoints."
The Instagram Basic Display API was deprecated on **2024-12-04**: "Instagram Basic
Display API has been deprecated. All requests ... will return an error."
(<https://developers.facebook.com/docs/instagram-platform/changelog>). A tutorial naming
either is more than eighteen months stale, and there are a great many of them.

### The choice is exclusive

> "Your app can either use Facebook Login or Instagram Login but not both."
>
> <https://developers.facebook.com/docs/instagram-platform/app-review/> (Updated
> 2026-06-30)

One app, one route, and no in-app path from one to the other. That sentence is the reason
the next section matters more than it looks.

### The carve-out that inverts the recommendation

Read this before choosing a route, because the obvious choice is wrong for a command line
tool the moment App Review enters the picture.

The Instagram Login route needs two scopes instead of five, no Facebook Page, no Page
access token and no `pages_*` permissions at all. On the Standard Access path that this
page recommends, it is the smaller thing to build. Research for this project stopped
there and recommended it outright.

Then there is this, on the Instagram Platform overview:

> "If reviewers are unable to test your app because it is behind a private intranet, **has
> no user interface**, or has not implemented Facebook Login for Business, you can request
> approval only for the following permissions:
>
> * `instagram_basic`
> * `instagram_manage_comments`"
>
> <https://developers.facebook.com/docs/instagram-platform/overview/>

"Has no user interface" is a literal description of a command line tool. The trigger is
untestability rather than privacy, and the two permissions named are both from the
**Facebook Login** family. Read straight, that is a carve-out for headless software: a
tool with no interface can be taken through App Review, on the Facebook Login route only.

The consequence for anyone building this: the route with the smaller Standard Access
setup is the route on which a headless tool cannot later be reviewed, and the choice
between them cannot be changed inside one app. If Advanced Access is ever plausible for
you, start on Facebook Login and pay the five scopes now. If it is not, Instagram Login
is fewer moving parts and stays fewer.

Earlier research read this sentence as a restriction on private apps and concluded that a
reviewable app has to be public. The words "private app" do not appear on the page. That
misreading inverted the entire App Review story for a headless tool, and correcting it is
the single most consequential change between the research and this page.

## Before you start

| You need | You do not need |
|---|---|
| An Instagram **professional** account, Business or Creator | A Facebook Page, on the Instagram Login route |
| A Meta developer account | A Business Manager account |
| An app you create yourself, of the **Business** type | A verified business, at Standard Access |
| A role on that app, and the Instagram account added to it | A public HTTPS endpoint, while you poll |
| Somewhere to run a redirect handler once, or the dashboard token button | Any hosting at all |
| Code you write yourself to call the API | Nothing in commentdraft reaches Instagram |

The app type is load bearing:

> "Business, Consumer, and Gaming apps are automatically approved for Standard Access for
> all permissions and features available to their app type."
>
> <https://developers.facebook.com/docs/graph-api/overview/access-levels>

> "If your current Meta app type is **not** a Business type app you will need to create a
> new app and select **Business** during the creation process."
>
> <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/get-started>
> (Updated 2024-12-02)

So is holding a role on it, and so is a second condition that is easy to read past. The
comment-moderation guide states the access level as depending on two things rather than
one:

> "Standard Access if your app serves Instagram professional accounts you own or manage
> **and have added to your app in the App Dashboard**."
>
> <https://developers.facebook.com/docs/instagram-platform/comment-moderation> (Updated
> 2025-06-02)

Adding yourself as a person with a role on the app is one step. Adding the Instagram
account to the app is a separate step in the dashboard, and skipping it leaves you
technically outside the sentence that keeps you out of App Review.

### Business or Creator

Either works. Both configurations state "Requires an Instagram Business or Creator
Account" (<https://developers.facebook.com/docs/instagram-platform>), and nothing on the
comment-moderation guide or on either comment reference distinguishes the two for reading
comments or posting replies. Neither type is required over the other for this job.

What switching costs the operator outside the API is a question this page cannot answer.
See [What is still unknown](#what-is-still-unknown). The widely repeated claim that
Business accounts have a reduced licensed music library relative to Creator accounts is
neither asserted nor denied here, because every Instagram Help Center page that would
settle it renders client-side and returned an empty shell. Read it in a browser before
switching if the account posts Reels with commercial music.

## Getting a token: Instagram API with Instagram Login

commentdraft ships no login helper for any platform, and would ship none for this one.
You perform this exchange yourself and put the result somewhere your own code reads.

1. Convert the Instagram account to a professional account, Business or Creator.

2. Create a Meta app at <https://developers.facebook.com/apps> and choose the **Business**
   app type.

3. Add the Instagram product, then open **Instagram > API setup with Instagram business
   login** in the App Dashboard.

4. Add yourself as a person with a role on the app, Administrator or Developer. This is
   what keeps you at Standard Access:

   > "Permissions with Standard Access can only be requested from app users who have a
   > role on the requesting app."
   >
   > <https://developers.facebook.com/docs/graph-api/overview/access-levels>

5. Add the Instagram account itself to the app in the same dashboard section, per the
   comment-moderation sentence quoted above.

6. For a single operator on their own account, take the short path: click **Generate
   token** next to the Instagram account, log in, and copy the token. That is a long-lived
   token valid for 60 days
   (<https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/get-started>).
   Steps 7 to 10 are the proper flow and can be skipped while it is one person on one
   account.

7. Configure Business Login for Instagram: an OAuth redirect URI, a deauthorize callback
   and a data deletion request URL. Send the operator to the authorization URL:

   ```
   https://www.instagram.com/oauth/authorize
     ?client_id={instagram-app-id}
     &redirect_uri={redirect-uri}
     &response_type=code
     &scope=instagram_business_basic,instagram_business_manage_comments
   ```

   <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login>

8. Exchange the authorization code for a short-lived token. The code is valid for 1 hour
   and is single use.

   ```
   POST https://api.instagram.com/oauth/access_token
     client_id, client_secret, grant_type=authorization_code, redirect_uri, code
   ```

9. Exchange the short-lived token for a long-lived one, valid for 60 days:

   ```
   GET https://graph.instagram.com/access_token
     ?grant_type=ig_exchange_token
     &client_secret={app-secret}
     &access_token={short-lived-token}
   ```

10. Refresh on a schedule, not on a failure:

    ```
    GET https://graph.instagram.com/refresh_access_token
      ?grant_type=ig_refresh_token
      &access_token={long-lived-token}
    ```

    Two preconditions, both from the business login page, and they bite from opposite
    directions. The token being refreshed must be "at least 24 hours old" and still valid,
    and the account must still have granted `instagram_business_basic`. And: "Tokens that
    have not been refreshed in 60 days will expire and can no longer be refreshed." A
    refresher that only fires on a 401 has already missed its window when it fires.

11. Get the account id. Read the next section before writing this call.

### The id that is not the id

`GET /me?fields=id` returns the wrong id, and nothing tells you.

On the Instagram Login route the get-started page carries a field table with two entries
that a reader skims past:

> `id`: "The app user's app-scoped ID"
>
> `user_id`: "The Instagram professional acount ID, `<IG_ID>`, for your app user. **This
> ID is value of the `id` field received in webhook notifications for this account.**"
>
> <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/get-started>
> (Updated 2024-12-02. The missing letter in "acount" and the missing "the" are Meta's,
> reproduced as read.)

The call to make is:

```
GET https://graph.instagram.com/v26.0/me?fields=user_id,username
```

and the value to keep is `user_id`. An implementer who follows the widely copied
`GET /me?fields=id` gets an app-scoped id, which will not match `entry.id` in any webhook
payload and does not address the account on `/{ig-id}/media`. The failure mode is a
handler that returns 200 to Meta forever and never recognises a single notification as
belonging to the account it is watching, and a media listing that comes back empty rather
than refused. Nothing raises. This is the most expensive line on the page to get wrong,
and the research this page is built on had it wrong.

## Getting a token: Instagram API with Facebook Login for Business

The route to take if App Review is ever plausible, per
[The carve-out](#the-carve-out-that-inverts-the-recommendation).

1. Create a Meta app of the **Business** type and configure its basic settings.

2. Add the **Facebook Login for Business** product and add your redirect URI to **Valid
   OAuth redirect URIs**.

3. Request the five scopes listed above, plus `pages_manage_metadata` if webhooks are in
   scope for you.

4. Run the login flow and obtain a user access token.

5. `GET /me/accounts` and keep the Page id.

6. `GET /{page-id}?fields=instagram_business_account` for the Instagram account id.

   <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/get-started>

Meta adds a prerequisite on that page that has nothing to do with scopes: "your Facebook
Developer account must be able to perform Tasks on the Facebook Page connected to the
Instagram account you want to query." `docs/platforms/facebook.md` has the task matrix and
which tasks mean what.

Token lifetimes on this route are Facebook's rather than Instagram's. Short-lived user
tokens last one to two hours, long-lived user tokens about 60 days, and a long-lived Page
token carries no expiry and is invalidated by events instead
(<https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived>).
The 90 day permission non-use rule applies here as it does to Pages, and
`docs/platforms/facebook.md` covers it in the detail it deserves.

## Reading comments

Two calls. Find the account's media, then read the comments on each.

```
GET https://{host}/v26.0/{ig-id}/media
GET https://{host}/v26.0/{ig-media-id}/comments
```

`{host}` is `graph.instagram.com` on the Instagram Login route and `graph.facebook.com`
on the Facebook Login route. Both samples on the comment-moderation guide read `v26.0`
(<https://developers.facebook.com/docs/instagram-platform/comment-moderation>, Updated
2025-06-02).

Comment fields available on
<https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-comment/>
(Updated 2025-01-21): `id`, `text`, `timestamp`, `from`, `hidden`, `like_count`,
`username`, `media`, `parent_id`, `replies`, `legacy_instagram_comment_id`.

Reading `username` needs the comments scope rather than the basic one, and has done since
**2024-08-27** (same page). An app that asked only for `instagram_business_basic` gets
comments with no author name on them, which is enough to make the `author` column of a
comments CSV empty for every row.

### What the comments edge will not do

Quoted from
<https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-media/comments/>
(Updated 2025-01-21):

> "Requests made using version 3.2+ will have results returned in reverse chronological
> order."
>
> "Returns only top-level comments. Replies to comments are not included unless you use
> field expansion."
>
> "Returns a maximum of 50 comments per query."
>
> "Comments cannot be filtered by timestamp."
>
> "Comments on live video IG Media are not supported."

Fifty per query with no timestamp filter is the shape of the whole read loop. There is no
incremental query, so you paginate everything and de-duplicate on comment id locally, on
every run. That is the same suppression `commentdraft pull --state` performs for Facebook
and the reason it exists at all; `docs/limits.md` covers what a state file can and cannot
promise.

Three more omissions, from the IG Comment reference (Updated 2025-01-21). Each removes
comments from the response without any error:

> "Comments created by IG Users who have been restricted by the app user will not be
> returned unless the IG Users are unrestricted and the Comments are approved"
>
> "Comments on age-gated media are not returned."
>
> "Requests cannot be performed on comments discovered through the Mentions API unless the
> request is made by the comment owner."

The restriction clause has two conditions rather than one. Unrestricting somebody is not
enough on its own; their comments also have to be approved. Research for this page dropped
the second half of that sentence, and the age-gated line entirely.

## Publishing a reply

```
POST https://{host}/v26.0/{ig-comment-id}/replies
Content-Type: application/json

{"message":"..."}
```

The reference page also documents the query parameter form,
`POST /{ig-comment-id}/replies?message={message}`
(<https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-comment/replies>).
The response carries the new reply's comment id. Posting to
`POST /{ig-media-id}/comments` instead creates a top-level comment on the media rather
than a reply, which is a different thing to do and not what a reply queue wants.

### Three constraints, all resting on a page from 2021

The write path's limitations come from one reference page, and that page carries
`Updated: Nov 9, 2021`. Four years and nine months old at the time of reading, and it
predates the Instagram Login route entirely: its own sample still posts to
`graph.facebook.com`. Take the three sentences seriously and confirm each against
behaviour before a design depends on it.

> "You can only reply to top-level comments; replies to a reply will be added to the
> top-level comment."
>
> "You cannot reply to hidden comments."
>
> "You cannot reply to comments on a live video; use the Instagram Messaging API to send a
> private reply instead."
>
> <https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-comment/replies>
> (Updated 2021-11-09)

The first one changes what an approval queue is allowed to offer. A reply approved against
a nested comment is silently re-parented to the top-level comment, so the reply is live,
it is under the wrong words, and the person who approved it saw something else on their
screen. `docs/platforms/facebook.md` describes the same failure on Facebook, where the
connector's answer is to hold back replies-to-replies rather than to offer a keystroke
that cannot do what it appears to do. Anyone building this connector should reach the same
answer for the same reason.

The second one is the reason to read the `hidden` field before drafting anything.
Instagram's own comment filters hide comments without being asked, so this is not a rare
state. Facebook's connector makes the opposite call on its own equivalent field and queues
hidden comments anyway, because discarding a customer's comment on a flag is the worse
failure there. The two platforms differ in whether the send is documented to fail, and
that is what the decision turns on.

## What you would have to build

The registry asks a connector for two methods, `fetch_comments(config, since)` and
`publish_reply(config, parent_id, text)`, described in
`src/commentdraft/platforms/__init__.py`. Rows come back in `engine.IN_FIELDS` shape:
`id`, `platform`, `author`, `comment`, `post_title`. Everything downstream of that is
already built and platform-blind.

What is specific to Instagram, beyond the HTTP:

1. Two calls per pull rather than one. Media first, then comments per media object, with
   pagination on both and the 50-per-query ceiling on the second.
2. De-duplication on comment id in the connector as well as in `--state`, because there is
   no timestamp filter to lean on and a `--since` marker cannot reduce a single API call.
3. `post_title` has no natural source. Instagram media has a caption rather than a title,
   and a caption is not a title. Decide what goes in that column and write it down.
4. `author` needs the comments scope, per the 2024-08-27 change above.
5. A decision on replies-to-replies, per the re-parenting sentence above.
6. A read-back after every write. Facebook's connector proves each write was a reply
   before reporting success, and the argument for that check is not Facebook-specific:
   a write path that lands somewhere other than where the approval said is silent by
   construction. `docs/platforms/facebook.md` has the full reasoning and the incident that
   produced it.

Nothing here is written. Point 6 in particular is a design commitment rather than a line
of code, and it is the part most likely to be skipped by somebody in a hurry.

## What breaks, and what each failure means

### Meta's own permissions reference is wrong about these two permissions

This is a defect on Meta's page, not a transcription error, and knowing it before you read
that page is worth more than anything else in this section. It was reproduced through two
independent extraction methods, in two sessions, at byte level.

Under `instagram_business_manage_comments`, the description sentence is the text belonging
to `instagram_business_content_publish`: "The **instagram_business_content_publish**
permission allows an app to create organic feed photo and video posts on behalf of a
business user." Its Allowed Usage row is content-publishing text too.

Under `instagram_manage_comments`, the Use Case Description asks you to "Provide specific
examples of why your app requires the `instagram_content_publish` permission to create and
publish organic feed photo and video posts", and screencast bullet 2 reads "Demonstrate
creating a new photo post and publish the post to the business user's Instagram feed".

<https://developers.facebook.com/docs/permissions/reference/instagram_manage_comments>
(the per-permission URLs all render the same single reference table)

What is comment-specific on those rows, and therefore what to trust: the dependency lists,
and the screencast bullets under `instagram_business_manage_comments`, which read
"Demonstrate creating a new comment, updating an existing comment and deleting a comment"
and "Show how this appears both in your app and the native Instagram app". Expect the
published screencast requirement for the Facebook Login comments scope to be wrong on the
page and to be about comments in the review itself. Re-reading the live page does not
resolve this, because the live page is the error.

Earlier research blamed its own fetch tooling for the mismatch and told a reader to
re-check in a browser. When two independent extraction methods agree on something that
looks like a tooling artifact, it usually is not one.

### The scope string on the App Review page does not match the permissions reference

The Instagram App Review page lists `instagram_business_content_publishing` and
`instagram_content_publishing`, with `-ing`. The permissions reference and the Platform
overview both use `instagram_business_content_publish` and `instagram_content_publish`,
without. Neither is a comment scope, so this costs nothing here, and it sits on the exact
page a reader opens to prepare a submission. Take every scope string from the permissions
reference and from nowhere else.

### The app-scoped id

Covered above under [The id that is not the id](#the-id-that-is-not-the-id). It belongs on
this list too, because it produces no error at any layer.

### Throttling

Error code **80002**, with `estimated_time_to_regain_access` in the
`X-Business-Use-Case-Usage` header giving minutes until access resumes
(<https://developers.facebook.com/docs/graph-api/overview/rate-limiting/>). Back off on
it. See the cold start problem in [Limits](#limits) for why this arrives sooner than
anybody expects.

### Old scope names

`business_manage_comments` and its siblings stopped working on 2025-01-27, and the
Instagram Basic Display API stopped working on 2024-12-04. Both are covered above. They
are listed again here because the symptom is an app that cannot call the endpoints at all,
and the cause is a tutorial rather than anything on your machine.

### Token invalidation

Meta does not publish the list. The access tokens page acknowledges that tokens "are still
subject to invalidation for other reasons" without enumerating them, and points at a
separate error-handling document whose documented URL returns 404. Whether a password
change, a scope change or a change in App Review status invalidates a token is
undocumented in both directions. Handle a sudden `OAuthException` at any time, and do not
build a recovery path that assumes it means one particular thing.

## Limits

`docs/limits.md` covers what commentdraft cannot do regardless of platform, including why
repetition across a batch can be reported and not prevented. This section is what Meta
imposes on Instagram.

### Rate limits

Instagram Platform uses Business Use Case rate limiting:

> "Calls within 24 hours = 4800 * Number of Impressions"

where Number of Impressions is

> "the number of times any content from the app user's Instagram professional account has
> entered a person's screen within the last 24 hours."
>
> <https://developers.facebook.com/docs/graph-api/overview/rate-limiting/>

Rolling 24 hour window, counted per Instagram professional account rather than per app.
Responses carry `X-Business-Use-Case-Usage`, whose JSON holds `call_count`,
`total_cputime`, `total_time` and `estimated_time_to_regain_access`.

**There is no minimum on the impressions term for Instagram.** The "minimum value for
impressions is 10" line that turns up in search results is in the **Threads** section of
the same page. The consequence is a cold start: an account with genuinely no impressions
in the last 24 hours has a budget the published formula puts at or near zero, and that is
precisely the state a new operator is in on day one, and the state a dormant account
returns to. Do not tell anyone a new account gets 48,000 calls a day. Design for backing
off on 80002 from the first call.

Business Discovery and Hashtag Search are excluded from Business Use Case limiting and use
Platform Rate Limits instead. Neither is relevant to reading comments.

### Quota costs per endpoint

**Unpublished.** No page assigns a point cost to an individual Instagram endpoint. The
model appears to be one call counting as one unit against the 24 hour budget, and no page
states that either. Cost is visible only as a percentage of an opaque budget in the header
above.

### Replies published per day

**Unpublished.** No per-day ceiling on public comment replies exists in Meta's developer
documentation, distinct from the call budget above.

The 750 per hour figure that circulates is for a different API:

> "Your app can make 750 calls per hour per Instagram professional account for private
> replies to comments on Instagram posts and reels."
>
> <https://developers.facebook.com/docs/instagram-platform/overview/>

Private replies send a direct message in response to a comment. Do not cite that number
for public replies.

The behavioural ceiling is the Community Standards spam policy, enforced without a
published number:

> "Posting, sharing, engaging with content or creating accounts, Groups, Pages, Events or
> other assets, either manually or automatically, at very high frequencies."
>
> <https://transparency.meta.com/policies/community-standards/spam/>

The same page adds that restrictions may reach lower-frequency accounts showing "other
indicators of Spam (e.g., posting repetitive content) or signals of inauthenticity". That
second sentence is the one that bites a drafting tool, and it is not about volume.
`docs/limits.md` explains why nothing in this design can prevent near-identical replies
while a draft is being written, and what the run report says about it afterwards.

### Webhooks, which you cannot have yet

The comments webhook requires Advanced Access, on both routes. Meta says so three times
across two pages.

> "Your app must have successfully completed App Review (advanced access) to receive
> webhooks notifications for `comments` and `live_comments` webhooks fields."
>
> <https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-instagram/>

> "Advanced Access is required to receive `comments` and `live_comments` webhook
> notifications"
>
> <https://developers.facebook.com/docs/instagram-platform/webhooks/> (Updated 2026-03-03)

The second page also carries a table row reading "Access level | Advanced Access for
`comments` and `live_comments`". Advanced Access needs App Review and Business
Verification, so a first version polls.

The failure mode if you try anyway is the reason this is stated so plainly. The webhook
endpoint verifies, the subscription call returns `{"success": true}`, and no event ever
arrives.

Four more conditions apply once you do have Advanced Access, all verbatim from the two
pages above:

> "Apps must be set to **Live** in the App Dashboard to receive webhook notifications"
>
> "The Instagram professional account that owns the media objects must be public to
> receive notifications for comments or @mentions."
>
> "Apps don't receive a webhook notifications if the Media where the comment or @mention
> appears was created by a private account."
>
> "You will not be able to query historical webhook event notification data"

And one that would matter more than all of them if it is current: "Reels are not
supported." That sentence is live today on the Facebook Login webhooks page and absent
from the Instagram Login one. Whether it still describes behaviour is unknown, and it is
in [What is still unknown](#what-is-still-unknown) for that reason.

Subscription differs by route. Instagram Login posts to `/me/subscribed_apps`:

```
POST https://graph.instagram.com/v26.0/me/subscribed_apps
  ?subscribed_fields=comments
  &access_token={access-token}
```

Facebook Login posts to the Page instead, with a Page access token and
`pages_manage_metadata`:

```
POST /{page-id}/subscribed_apps
  ?subscribed_fields={fields}
  &access_token={page-access-token}
```

The payloads differ too, and one parser will not read both. On the Instagram Login route
`field` and `value` sit directly on the entry; on the Facebook Login route they are nested
inside a `changes` array. On the Instagram Login route `mentions` is not separately
subscribable at all: the webhooks field table gives its Instagram Login permission cell as
"Included in the `comments` webhook notification".

## App Review, if you ever need it

Only for Advanced Access, which means only for the webhook or for serving accounts you do
not own. The requirements are confirmed on a page Meta updated 2026-06-30
(<https://developers.facebook.com/docs/instagram-platform/app-review/>):

1. App settings complete: an app icon at 1024x1024, a Privacy Policy URL, an App Category
   and a Business Email.
2. "detailed step-by-step instructions for Meta reviewers to log in and test your app".
3. A screencast per permission demonstrating that permission in use, in an English
   interface where possible, with captions and tool-tips where the interface is not
   self-explanatory.
4. Test credentials where applicable.

The same page carries the note that decides the route, and it is the other half of the
carve-out above:

> "Web or mobile Web is the only platform that currently supports Instagram API with
> Instagram Login."
>
> <https://developers.facebook.com/docs/instagram-platform/app-review/>

A terminal tool has no web platform for a reviewer to look at. Combined with the carve-out
sentence, that leaves one workable answer: a headless tool that needs Advanced Access goes
through review on the Facebook Login route, for `instagram_basic` and
`instagram_manage_comments`. On the Instagram Login route it would need a web interface
built for no reason other than to be reviewable, and the route cannot be changed within
one app.

**How long review takes is unpublished.** No page on developers.facebook.com states a
turnaround for Instagram App Review or for Business Verification. Any figure you have seen
is somebody's anecdote, and it is worth remembering that a rejection restarts whatever
clock exists.

## Policy

`docs/platform-policy.md` maps each safety property in this repository to the clause it
exists for, including Meta's Developer Policy 1.7 on consent before acting on somebody's
behalf. It is not repeated here. What follows is what was found specifically for
Instagram, on 2026-08-01.

The Meta Platform Terms (<https://developers.facebook.com/terms/>) bind API access. Clause
3.a.viii prohibits "Processing Platform Data for purposes other than the applicable
permitted purposes set forth in Meta's Developer Docs". Reading the comments on your own
media in order to answer them is the permitted purpose the comments permission is
described by, defect in that description notwithstanding. The Terms carry a Last Updated
stamp that did not survive extraction and is not printed here.

Meta Developer Policies (<https://developers.facebook.com/devpolicy/>) clause 2.7:

> "Don't participate in any program that promotes or facilitates the purchase, sale, or
> exchange of 'Likes', 'Shares', 'Followers', 'Comments', 'Accounts', 'Pages', 'Profiles',
> 'Groups'..."

The clause number is confirmed structurally: that sentence is item 7 under the top-level
heading "2. Encourage proper use". The Developer Policies page carries no last-updated
date anywhere in its text, so it is cited undated on purpose.

The Community Standards spam policy is quoted in [Limits](#limits). Its construction is
worth reading closely: the prohibition names frequency and inauthenticity, and it
explicitly contemplates that doing something "either manually or automatically" can be
acceptable. What makes it a violation is "at very high frequencies", plus the separate
sentence about repetitive content that applies at any frequency.

**No disclosure requirement was located.** The Platform Terms, the Developer Policies, the
spam standard and the inauthentic behaviour standard were searched for any clause
requiring an account to disclose that a reply was drafted by software. None applying to
public Instagram comments was found. That is an absence of a found clause rather than
proof of absence. One signal of direction: a June 2026 changelog entry added an
`is_ai_generated` parameter to the Content Publishing API
(<https://developers.facebook.com/docs/instagram-platform/changelog>). That is for media
rather than for comments, and this section is worth re-reading periodically. Operators in
regulated sectors should take their own advice rather than this page's.

## What is still unknown

Every item here failed to resolve against a primary source, or cannot resolve without a
live call. None of it is smoothed over above.

**Whether the 2021 reply limitations still hold.** The three sentences governing the write
path sit on a page Meta last updated 2021-11-09, predating the Instagram Login route. One
reply posted against a throwaway media object settles the re-parenting sentence, and one
against a hidden comment settles the second. Nobody with credentials has made either call.

**Whether the `comments` webhook echoes the operator's own replies.** Four webhook pages
say nothing either way. Assume echoes are possible and de-duplicate on comment id.

**Whether "Reels are not supported" is factually current.** The sentence is live on the
Facebook Login webhooks page and absent from the Instagram Login one. If it is current,
webhooks miss most of what happens on a modern account, and polling is unaffected either
way. Only a live subscription test settles it.

**Whether switching to a Business account costs the operator a restricted music library,
and whether Creator differs.** Three Instagram Help Center articles
(`help.instagram.com/402084904469945`, `/138925576505882`, `/502981923235522`) were
attempted and each returned an empty client-side shell. Search snippets suggest a
distinction exists. Nothing here asserts it in either direction. A verifier later noted
that `help.instagram.com` article pages do render through a text-extraction proxy, so this
is retrievable by whoever needs it; it was not pursued because it is a product question
rather than an API one. Open the page in a browser before advising anyone to switch.

Separately, the claim that professional accounts get less reach than personal ones has no
Meta source behind it and is not repeated here.

**Business Verification: which documents are accepted, whether a sole trader without a
registered company can complete it, and how long it takes.** Meta's developer page defers
to the Business Manager Help Center
(<https://developers.facebook.com/docs/development/release/business-verification>), and
the Help Center article returned a client-side shell. This matters only for the Advanced
Access path.

**The canonical list of events that invalidate a token.** Covered under
[What breaks](#what-breaks-and-what-each-failure-means). The document Meta points at for
it returns 404 at the URL Meta gives.

**Per-endpoint quota weights.** No page assigns point costs to individual Instagram
endpoints.

**Whether Instagram Platform access is free.** No pricing page exists, no metering
documentation exists, and no fee is mentioned on the Instagram Platform overview or the
product page. That is an absence of evidence rather than a statement of price. Meta
nowhere says this is free. Budget for the possibility that it changes with a version.

**Whether the comment-moderation guide's limitations are complete.** That page carries
permissions, samples and the webhook recommendation, and no consolidated limitations
block. Every limitation quoted on this page comes from the older
`instagram-graph-api/reference/...` pages instead, dated 2025-01-21 and 2021-11-09. A
constraint that exists only on the newer Instagram Login documentation would not have been
found by this pass.

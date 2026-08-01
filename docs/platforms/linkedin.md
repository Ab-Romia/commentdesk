# LinkedIn Pages and profiles

What it takes to read the comments on posts a LinkedIn Page or profile published, and
what stops most readers of this page from ever getting there.

LinkedIn versions the Community Management REST surface by month. The version current
at the time of writing is **`202607`**, sent as the `Linkedin-Version` header on every
call
(<https://learn.microsoft.com/en-us/linkedin/marketing/versioning?view=li-lms-2026-07>,
`ms.date: 2026-07-13`). A version is supported for "a minimum of one (1) year", and
`202507` is already sunset. Every `learn.microsoft.com` page cited below was read on
**2026-08-01**. Those pages carry an `ms.date` in their own source, and it is given
next to the link where it matters, because two of them carry a fresh stamp over a body
written in 2022. The legal pages carry revision dates of their own and those are given
too.

## There is no LinkedIn connector

commentdraft ships exactly one connector and it is Facebook. There is no LinkedIn code
in this package: no client, no token handling, no endpoint, no error table, no tests.
`platform = "linkedin"` is not something you can write in `[source]` or `[publish]` and
have work. Both `commentdraft pull` and `commentdraft publish` refuse it before
anything is called:

```
unknown platform: linkedin. registered: facebook
```

That is exit code 2, a setup that never reached a platform. Nothing on this page
describes code that exists. It is the access research, written so that whoever builds
the connector, or decides against it, starts from LinkedIn's primary sources instead of
from a blog post.

What does work today, with no LinkedIn access of any kind, is everything from the
comments CSV onward. `commentdraft run`, `review`, `chat`, `ui` and `bakeoff` never
touch a platform:

```bash
commentdraft run --config config.toml --comments comments.csv --out out
commentdraft review out/review.csv --out out
```

Build `comments.csv` by hand in the five columns `docs/comments-csv.md` documents, draft
against it, read the review page, and type the replies you approve into LinkedIn
yourself. The storage rules in
[The storage rules](#the-storage-rules-and-what-they-do-to-a-review-queue) are conditions
attached to API access, so a person copying text out of their own browser is not the
party those conditions bind. Everything else on this page is.

## What the access costs, and who cannot get it

The Community Management API is the only documented way to read LinkedIn comments
programmatically. Access to it is a two stage partner review with a human on the other
end of both stages, in this order:

| Stage | What you get | What LinkedIn checks |
|---|---|---|
| Development Tier, the tier every new applicant starts in | 500 API calls per app per 24 hours, 100 per member per 24 hours. Push notifications off. `BATCH_GET` methods off. Up to "twelve (12) months max" | "Approved use case; Verified business email address; Verified organization; Verified organization website and domain address; Application verified by LinkedIn Page associated with same organization" |
| Standard Tier | The production quota, which LinkedIn does not publish. Webhooks. Batch reads | "Approved use case; Valid privacy policy; Compliance with our terms, restrictions, security, privacy, and trust requirements, and data storage requirements; Screen recording that accurately demonstrates all core functionality" |

Both quoted criteria lists are from
<https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-07>
(`updated_at: 2026-02-11`). The Development Tier restrictions are from the migration
guide, and one of them carries a caveat: see [Limits](#limits).

Two sentences decide whether the rest of this page is worth your afternoon.

> "At this time, our Community Management APIs are only available to registered legal
> organizations for commercial use cases only."
>
> <https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-07>

> "Personal email addresses won't pass the vetting process."
>
> Same page.

A sole trader with no registered legal entity does not qualify as documented, and no
amount of building qualifies them. Neither does a hobby use case, a personal brand, or
a portfolio project: the words are "commercial use cases only". If that is you, stop
here and use the manual path in the section above. It costs you a copy and paste per
comment and it asks nobody for permission.

One more thing to know before you spend a week on this. A rejection is terminal for
that developer app, at both tiers:

> "You won't be able to re-apply for Development tier access with your existing app."
>
> Same page.

A rejected submission burns the app identity. You create a new app and redo the Page
verification underneath it.

## What is verified here, and what is not

**Nobody has applied for either tier, held a LinkedIn access token, or made a single
call.** Not one sentence on this page reports observed behaviour of the live API. Every
number and quoted string below was read off LinkedIn's own documentation and then read
again, on the same day, by a second pass that re-fetched the sources independently and
corrected six claims in the first.

Verified against LinkedIn's live documentation, read 2026-08-01:

| What | How far the check went |
|---|---|
| Endpoint paths, HTTP methods and the header trio | Read on the Comments API reference and re-read at the `202607` view |
| Scope strings | Read character for character on the Comments API permissions table and the migration guide's rename table |
| Error rows | Quoted as LinkedIn writes them, including two of LinkedIn's own typos |
| The two stage review and its criteria | Read on the app review page, with the `updated_at` stamp checked in page source |
| Quoted policy text | Fetched as raw text with `curl` rather than as a summary of the page, and quoted with the revision date printed on the document |
| Page dates | Taken from `ms.date` and `updated_at` front matter rather than inferred, which is how the 2022 bodies under 2026 stamps were caught |

Not established, and this list is complete:

- Whether `r_member_social_feed` is granted in practice to an applicant who asks. It is
  restricted and vetted, the request flow is behind an authenticated portal, and nobody
  has walked it.
- Whether Development Tier apps receive programmatic refresh tokens at all. LinkedIn
  offers them to "all approved Marketing Developer Platform (MDP) partners" and never
  says whether Development Tier counts as approved.
- Whether push notifications and `BATCH_GET` are genuinely off during Development Tier.
  One document says so and it is a 2022 body under a 2026 stamp. See
  [Limits](#limits).
- How long either review takes. LinkedIn publishes no SLA for Community Management
  review on any page read here.
- What the per-minute comment creation throttle actually is. The error message for
  hitting it is published; the number is not.
- Whether a LinkedIn password change invalidates a live token. Neither OAuth page
  mentions it in either direction.
- Whether losing a tier after a compliance review revokes tokens already issued, or
  blocks new ones.
- What any of this costs. See [What is still unknown](#what-is-still-unknown).

## Before you start

| You need | Where that comes from |
|---|---|
| A registered legal organization and a commercial use case | The app review quote above |
| A business email address on that organization's own domain | "Personal email addresses won't pass the vetting process." |
| A LinkedIn Page for the organization, and a super admin of it who will verify your app against it | Quick start, steps 1 and 3 |
| An organization role on that Page: `ADMINISTRATOR` or `DIRECT_SPONSORED_CONTENT_POSTER` for reading | The Comments API permissions table |
| A published privacy policy | Standard Tier criteria |
| A working app, far enough along to film | Standard Tier screencast |
| Test credentials a stranger can sign in with | Standard Tier, a standing requirement |
| Patience for up to twelve months of Development Tier limits | The migration guide's tier table |

The Page and the app are separate objects that have to be tied together by hand, and
the tie cannot be made through the API:

> "Access to a Company Page cannot be granted or updated through the API. Please use
> the UI tool to grant, update, or remove access."
>
> <https://learn.microsoft.com/en-us/linkedin/marketing/quick-start?view=li-lms-2026-07>

### Which organization roles work

LinkedIn controls organization access by role. The definitions are verbatim from
<https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/organization-access-control-by-role?view=li-lms-2026-07>
(`ms.date: 2026-04-29`):

| Role | What LinkedIn says it does | Can read comments | Can publish replies |
|---|---|---|---|
| `ADMINISTRATOR` | "Access to administer an organizational entity. An administrator can post updates, edit the organization's page, add other admins, view analytics, and view notifications." | Yes | Yes |
| `DIRECT_SPONSORED_CONTENT_POSTER` | "Access to read and create direct sponsored content (DSC) for an organizational entity." | Yes | Yes |
| `RECRUITING_POSTER` | "Access to post to an organizational entity." | No | Yes |

The last row is the trap. `w_organization_social_feed` accepts all three roles.
`r_organization_social_feed` names only the first two. An admin who grants the
posting-shaped role to the person authorizing your app produces a setup that can send
replies and cannot see the comments to reply to, and the symptom is an empty comment
list rather than a permission error.

Webhook subscription needs a third thing again: `rw_organization_admin`, "Restricted to
organizations in which the authenticated member has the following role: -
ADMINISTRATOR".

## Getting access

Ten steps, and only the first two are quick.

1. Create a LinkedIn Page for the organization, if one does not exist
   (<https://www.linkedin.com/help/linkedin/answer/a543852>). Every read endpoint below
   is scoped to an organization.

2. Create a developer application at <https://www.linkedin.com/developers/apps/new>.

3. Have a super admin of that Page verify the app against it, in the LinkedIn UI
   (<https://www.linkedin.com/help/linkedin/answer/a548360/associate-an-app-with-a-linkedin-page>).
   Development Tier vetting checks for this specifically, in the words "Application
   verified by LinkedIn Page associated with same organization".

4. On the app's Products tab, request the **Community Management API** product. That
   opens the Development Tier access request form.

5. Wait for the Development Tier decision. LinkedIn checks the five items in the table
   above. The business email is the item that fails people who are otherwise eligible,
   and a rejection here costs you the app.

6. Build against Development Tier limits: 500 calls per app per 24 hours, 100 per
   member per 24 hours, no push notifications, no `BATCH_GET`. The migration guide caps
   this stage at "twelve (12) months max", so a build that stalls has an expiry on it.

7. Film the screencast. LinkedIn publishes the shot list, and it is specific. For a
   Page use case:

   > "Demonstrate an application user approving access to their LinkedIn page data via
   > the complete OAuth flow. Demonstrate a user posting to their LinkedIn page via
   > your app. Demonstrate how a comment on that post by a member is displayed to users
   > in your app. Demonstrate what personal data fields from the commenter's LinkedIn
   > profile are displayed to users in your app."
   >
   > <https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-07>

   The profile use cases, Executive Management and Employee Advocacy, publish the same
   four shots with "profile" in place of "page" and "another member" in place of "a
   member". Read the fourth shot twice. LinkedIn is asking you to show, on camera,
   which fields of a commenter's profile your interface puts on a screen, and it is the
   same question the 24 hour caching rule asks in
   [The storage rules](#the-storage-rules-and-what-they-do-to-a-review-queue). An
   application that shows a commenter's name, headline and photo in a review queue is
   answering that question whether or not its author thought about it.

   Screencast rules, same page: high resolution, downloadable, only your own app's
   screens visible, narration recommended.

8. Supply test credentials. This is a standing requirement rather than something you
   wait to be asked for:

   > "Prepare to provide a company and product overview, description of your use case,
   > and test credentials for our reviewers to review your application."
   >
   > Same page.

   For a command line tool with an approval keystroke in the middle, work out early
   what "test credentials for our reviewers" is going to mean. LinkedIn's shot list and
   its credential request both assume an application a reviewer signs into.

9. Submit the Standard Tier access request form, with the recording. LinkedIn checks
   the four items in the table above, and the third of them names the data storage
   requirements explicitly.

10. Expect a technical sign off on top of the two forms. LinkedIn is rolling out a
    process with a live demo to a Business Development contact, checked against a
    numbered rule list running `CM-001` to `CM-028` covering OAuth handling, token
    refresh and expiry detection, notification handling and outage recovery. It is
    documented on the Community Management requirements page in the same doc set
    (<https://learn.microsoft.com/en-us/linkedin/marketing/community-management/integration-requirements-community-management?view=li-lms-2026-07>,
    `ms.date: 2026-03-25`). LinkedIn's own words for what the demo is:

    > "When you're nearing completion, you must initiate a Technical Sign Off request by
    > contacting your LinkedIn POC on the Business Development team. A demo will be
    > scheduled during which you'll be asked to showcase all your product capabilities.
    > During this evaluation, LinkedIn can suggest modifications which should be
    > completed for the sign off."

**How long all of this takes is unpublished.** No page read here states a number of
days for either review. A figure of "up to 30 business days" circulates, and it comes
from the separate Advertising and Marketing partner program application, not from
Community Management. Treat any total elapsed time you have been told as somebody's
anecdote, and plan around two sequential human reviews with their own rounds of
back-and-forth plus however long it takes you to build enough product to film.

## The scopes

Copy these character for character. Two of the names in wide circulation have been
dead for three years and will fail at review time.

| Scope | What LinkedIn says it does |
|---|---|
| `r_organization_social_feed` | "Retrieve organizations' posts, comments, and reactions. Restricted to organizations in which the authenticated member has one of the following company page roles. - ADMINISTRATOR - DIRECT_SPONSORED_CONTENT_POSTER" |
| `w_organization_social_feed` | "Post, comment, and react on posts on behalf of an organization. Restricted to organizations in which the authenticated member has one of the following company page roles: ADMINISTRATOR, DIRECT_SPONSORED_CONTENT_POSTER, RECRUITING_POSTER." |
| `r_member_social_feed` | "Restricted Retrieve posts, reactions, and likes on behalf of an authenticated member. This permission is granted to select developers only." |
| `w_member_social_feed` | The member-side write scope, listed on the same permissions table |
| `rw_organization_admin` | Required to subscribe to the notifications webhook |

Source for all of them:
<https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/comments-api?view=li-lms-2026-07>
(`ms.date: 2026-04-28`).

### The names that are three years stale

| Do not send | Send instead | Deprecated |
|---|---|---|
| `r_organization_social` | `r_organization_social_feed` | June 2023 |
| `w_member_social` | `w_member_social_feed` | June 2023 |

Both renames are in the rename table on
<https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-api-migration-guide?view=li-lms-2026-07>.
`w_member_social` in particular is still described all over the web as the open,
self-serve permission for posting as a member. It is the old MDP name, superseded, and
no current page presents it as self-serve. Sending it is a straightforward failure.

### Personal profiles sit behind the same review, under a different use case

This is the claim most third-party writeups get wrong, and the mistake comes from two
permissions whose names differ by one word.

`r_member_social` is the legacy Member Feed Management permission and it is closed:

> "How do I get access to the Member Post Management program? `r_member_social` is a
> **closed** permission. We're not accepting access requests at this time due to
> resource constraints."
>
> <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview?view=li-lms-2026-07>
> (`ms.date: 2026-03-31`), FAQ 6

`r_member_social_feed` is the current permission, and its own table says "Restricted",
"granted to select developers only". Restricted and vetted describes a door with a
reviewer behind it. Closed describes a door nobody is answering. LinkedIn documents
personal profiles as an approvable surface in three separate places: Member Profile
Management is a named product in the Marketing API Terms, Profile Management is a named
approved use case on the Community Management overview, and the app review page
publishes Standard Tier screencast shot lists for two profile-based use cases,
Executive Management and Employee Advocacy. Those shot lists include demonstrating
"how a comment on that post by another member is displayed to users in your app",
which is this project's loop on a personal profile, described by LinkedIn as something
you film and submit.

The honest position on a personal profile is therefore restricted, vetted, granted to
select developers, harder than the Page path, and no guarantee of a grant. Writeups
calling it closed have read the wrong permission name. The
registered-legal-organization requirement still applies on top of it, so none of this
opens a route for an unincorporated individual.

## Getting a token

Standard 3-legged OAuth 2.0 authorization code flow. commentdraft ships no login
helper for any platform, and a LinkedIn connector would need this exchange performed
once by hand and the result put in an environment variable.

1. Send the member to the authorization screen:

   ```
   GET https://www.linkedin.com/oauth/v2/authorization
   ```

2. Exchange the code, which expires quickly:

   ```
   POST https://www.linkedin.com/oauth/v2/accessToken
   ```

   > "the authorization code has a 30-minute lifespan and must be used immediately"
   >
   > <https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow>
   > (`ms.date: 2025-11-10`)

3. Send the resulting bearer token, with the version and protocol headers, on every
   call:

   ```
   Authorization: Bearer {token}
   Linkedin-Version: 202607
   X-Restli-Protocol-Version: 2.0.0
   ```

| Lifetime | Value |
|---|---|
| Authorization code | 30 minutes |
| Access token | "Currently, all access tokens are issued with a 60-day lifespan" (`expires_in: 5184000`) |
| Programmatic refresh token | 365 days, measured from the original grant and never extended by a refresh |

The refresh window is the one that surprises people. Refreshing an access token does
not restart the refresh token's own clock, so a setup that has been refreshing happily
all year hits a wall:

> "you must get your application reauthorized by the member using the authorization
> flow"
>
> <https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens>
> (`ms.date: 2025-05-31`)

Put that date in a calendar. It is the LinkedIn equivalent of Facebook's 90 day
permission rule: nothing breaks, no code changes, and one day the replies stop.

What invalidates a token, from primary sources:

| Cause | What LinkedIn says |
|---|---|
| Asking for a different scope set | "If you request a different scope than the previously granted scope, all the previous access tokens are invalidated." |
| The member revoking your app | A 401 "indicates that your application is no longer authorized by the member" |
| The member losing the organization role | A 403 "indicates that the member is no longer an administrator of the company" |
| LinkedIn deciding to | "LinkedIn reserves the right to revoke Refresh Tokens or Access Tokens at any time due to technical or policy reasons." |

The first row bites during ordinary development. Adding `r_organization_social_feed`
to an app that launched with only the write scope invalidates every token every member
has already granted, rather than only the one whose scope changed, and every one of
them walks the consent screen again.

## Reading comments

Comments live on the versioned REST surface under `socialActions`. Three shapes, all
from the Comments API page cited above:

```
GET https://api.linkedin.com/rest/socialActions/{shareUrn|ugcPostUrn|commentUrn}/comments
GET https://api.linkedin.com/rest/socialActions/{shareUrn|ugcPostUrn|commentUrn}/comments/{commentId}
GET https://api.linkedin.com/rest/socialActions/{shareUrn|ugcPostUrn|commentUrn}/comments?ids=List({commentId})
```

Replies under a comment come from the same first call with a `commentUrn` in the URL
instead of a share URN. A `commentUrn` is composite: the thread's activity URN and the
comment id together.

The third shape, batch get, is unusable at Development Tier. Anything you build on it
works only after Standard Tier is granted.

### Webhooks, which are for organizations only

The Organization Social Actions Notifications API pushes new-comment events for Company
Pages. There is no member-profile equivalent documented anywhere, and searching for one
returned nothing, which is a negative finding rather than a confirmed absence.

Subscribe with a single composite-key PUT:

```
PUT https://api.linkedin.com/rest/eventSubscriptions/(developerApplication:urn:li:developerApplication:{id},user:urn:li:person:{id},entity:urn:li:organization:{id},eventType:ORGANIZATION_SOCIAL_ACTION_NOTIFICATIONS)
```

with body `{"webhook": "https://..."}`. The `action` values worth handling are
`COMMENT`, `COMMENT_EDIT`, `COMMENT_DELETE` and `ADMIN_COMMENT`. Three sentences from
that page decide how you write the receiver
(<https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/organization-social-action-notifications?view=li-lms-2026-07>,
`ms.date: 2026-06-10`):

> "Webhook events for `LIKE`, `COMMENT`, and `SHARE` actions are only triggered for
> posts with `visibility` set to `PUBLIC`."

> "LinkedIn will attempt to redeliver the notification once every 5 minutes for 8
> hours, after which redelivery attempts for that notification will be aborted."

> "Notifications sent to each webhook are batched by the event type ... with a batch
> size of 10."

A pull fallback exists and LinkedIn scopes it narrowly, "to bootstrap initial
notifications ... and for error handling", with a 60 day retention window on what it
can hand back:

```
GET https://api.linkedin.com/rest/organizationalEntityNotifications?q=criteria&actions=List(COMMENT,...)
```

Webhooks are also reported off during Development Tier, which means polling `GET
.../comments` under a 500-call daily budget is the only working read path for the whole
of the first stage. See [Limits](#limits) for why that particular claim carries a
caveat.

Building the receiver at all means a public HTTPS endpoint with a certificate LinkedIn
accepts, a challenge response, and deduplication across a batch size of 10 with an
8 hour redelivery tail. commentdraft polls on Facebook for smaller reasons than these;
`docs/platforms/facebook.md` sets out that argument.

## Publishing a reply

One endpoint, and it is the same one that creates a top-level comment:

```
POST https://api.linkedin.com/rest/socialActions/{shareUrn|ugcPostUrn|commentUrn}/comments
```

| Body field | Required | What it carries |
|---|---|---|
| `actor` | Yes | The organization or person URN the comment is authored by |
| `object` | Yes | The share or ugcPost URN the comment sits on |
| `message.text` | Yes | The text |
| `parentComment` | No | The composite URN of the comment being answered |
| `content` | No | An image, and see below |

`parentComment` is what makes a reply a reply rather than another top-level comment on
the post. Its shape is the composite URN:

```
urn:li:comment:(urn:li:activity:6305471423192264704,6308007194273021952)
```

The new comment's id comes back in the `x-restli-id` response header, with the full
comment object in the body. That header is what a connector would write into
`out/published.jsonl` as the published id, which is the record an operator needs when
somebody complains about something their own account posted.

Editing and deleting a comment both exist: `POST .../comments/{id}` with a
`PARTIAL_UPDATE` method header and a `$set` patch body, and `DELETE .../comments/{id}`.
On the documented shapes, the failure that dominates the Facebook connector, an edit
that silently overwrites a customer's own words, does not arise the same way here:
LinkedIn puts the update behind a different URL and an explicit method header rather
than behind the same call a create uses. That is a reading of two reference pages and
not an observation. Nobody has made either call, and a write check that reads the
result back is worth building anyway; `docs/platforms/facebook.md` sets out why.

Send text and nothing else. The schema accepts a `content` field and inline comment
images are not supported, so the failure is at creation time:

> "403 | Unpermitted fields present in REQUEST_BODY: Data Processing Exception while
> processing fields [/content] | Occurs when attempting to include an image in an
> inline comment which is not currently not supported by the API."
>
> Comments API page. The double negative is LinkedIn's.

## The storage rules, and what they do to a review queue

This is the section that decides whether a LinkedIn connector can look anything like
the Facebook one, and it is the part that no third-party writeup covers.

LinkedIn's Data Storage Requirements set **two different durations** on the two kinds of
data a comment arrives with
(<https://learn.microsoft.com/en-us/linkedin/marketing/data-storage-requirements?view=li-lms-2026-07>,
`ms.date: 2022-12-09`, `updated_at: 2026-02-02`):

| Row | Duration |
|---|---|
| "Members' Social Activity Data ... including articles, posts/shares, likes, comments, mentions, and the metadata relating thereto" | **48 Hours** |
| "Other Members' Profile Data" | **24 Hour Caching** |

The second row does more than shorten the clock. Its own words:

> "For clarity, nothing in these requirements or the LI MDP Terms shall permit you to
> cache this data in excess of 24 hours or store this data"

Caching for up to 24 hours is permitted. Storing it is not permitted at all. And where
a field could be read as falling under both rows, the page forecloses the argument:

> "if a given data field is encompassed by two or more of the following requirements,
> the shortest storage/caching duration shall apply"

### What that reaches in this repository

A commentdraft run leaves five things on disk. Every one of them is in scope.

| Artifact | What is in it | Which rule reaches it |
|---|---|---|
| `comments.csv` | `id`, `platform`, `author`, `comment`, `post_title` | The comment and its id are Social Activity Data, 48 hours. `author` is another member's profile data, 24 hours and cache only |
| `out/review.csv` | Every input column plus the decision, the draft and the model accounting | Same, and this is the file a reviewer opens tomorrow |
| `out/review.html` | The rendered review page, comment and author on screen | Same. This is also the file the Standard Tier screencast asks you to film |
| `pull-state.json` | Every comment id ever pulled, forever, by design | Comment metadata with no expiry on it at all |
| `out/published.jsonl` | `parent_id`, the reply text, timestamps, append only | The reply text is yours. `parent_id` is a comment id |

The `author` column is the sharp end. `docs/comments-csv.md` documents it as an input
column and the review page renders it, because knowing who wrote a comment is most of
what a person needs to answer one. Under the 24 hour caching row that column is the one
piece of a LinkedIn pull that may not be written down at all in the ordinary sense of
the phrase, and under the shortest-duration rule it drags any row that carries it down
to the shorter limb.

The two append-only files are the harder problem, because both exist for reasons this
project argues for elsewhere. `pull-state.json` is what stops a scheduled pull from
drafting and billing the same comment twice, and `docs/limits.md` says in as many words
that it "grows by one line per comment ever pulled and never shrinks by itself".
`out/published.jsonl` is the audit trail, and `docs/platform-policy.md` maps it to the
consent clauses it exists to satisfy: the question it answers is "what did my account
post", asked months later. Whether a bare comment id, with no text and no author beside
it, counts as "the metadata relating thereto" is not defined on LinkedIn's page. Both
readings are available and the strict one is the one a reviewer would take.

A LinkedIn connector is therefore not the Facebook connector pointed at a different
host. At minimum it needs the commenter's identity never written to disk, a purge older
than 48 hours over the CSVs and the rendered page, and an answer for the state file and
the audit file that this project does not currently have. The review-queue SLA falls
out of the same arithmetic: a comment pulled on Friday afternoon and approved on Monday
morning has been stored past both limbs, and nothing in commentdraft today would say a
word about it.

## What breaks, and what each failure means

| Symptom | What it means | What you do |
|---|---|---|
| A 200 with an empty comment list | The authorizing member holds `RECRUITING_POSTER` and not one of the two reading roles | A Page admin changes the role in the LinkedIn UI. The API cannot do it |
| 401 | "your application is no longer authorized by the member" | Walk the OAuth flow again |
| 403 | "the member is no longer an administrator of the company" | Restore the role first. A new token fails identically |
| 403 naming `[/content]` | An image in an inline comment | Send text only |
| 429 with "Comment create throttled: creation rate limit exceeded for member" | "Indicates member has hit the short term 1 minute rate limit for common creation." LinkedIn's typo, kept | Wait. The number is unpublished |
| 429 with no such message | The daily app or member quota | Both reset at midnight UTC |
| Every token stops working after you edited the scope list | "all the previous access tokens are invalidated" | Every authorized member re-consents |
| Replies stop roughly a year after launch | The refresh token's fixed 365 day window closed | Full re-authorization by the member |
| A rejected access request | Terminal for that app at either tier | New app, new Page verification, new submission |

The 429 rows are the ones to instrument. LinkedIn's usage alerts fire at 75 percent of
quota, they are not real time, LinkedIn states an expected delay of one to two hours,
and they fire on application-level breaches only:

> "Alerts are triggered only on application-level threshold breaches, not on
> member-level or combined member+app-level breaches."
>
> <https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits>
> (`ms.date: 2025-06-18`)

The 100 calls per member per 24 hours ceiling at Development Tier therefore gives no
warning at all before it bites, and it is the ceiling a single-operator setup reaches
first.

## Limits

`docs/limits.md` covers what commentdraft cannot do regardless of platform. This
section is what LinkedIn imposes.

### Rate limits

| Tier | Per app | Per member | Reset |
|---|---|---|---|
| Development | 500 calls / 24 hours | 100 calls / 24 hours | Midnight UTC |
| Standard | **Unpublished** | **Unpublished** | Midnight UTC |

The Development figures are corroborated twice, on the Community Management overview
FAQ 3 and on the migration guide, which states them as "500 API calls for an app for 24
hrs. 100 API calls per member of an App for 24 hrs."

Standard Tier limits are set per app, and the only place yours is written down is the
Developer Portal:

> "Standard rate limits are not published in documentation. You can look up the rate
> limit of any endpoint your app has access to through the Developer Portal ... This
> page will only show usage and rate limits for endpoints you have made at least 1
> request to today(UTC)."
>
> <https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits>

There is no way to look up an endpoint's limit before you call it. You spend a call
against production to find out what your budget was.

### Comments created per minute

**Unpublished.** The error exists, the message is quoted above, the number is on no
page found. Anything specific you have read for it is folklore.

### What Development Tier turns off

Two restrictions, from the migration guide's tier table: "Webhooks for Social Actions |
Push notifications for Social Actions disabled | During the Development Tier or 12
months max", and "No API calls with BATCH_GET method allowed".

Both carry a caveat worth stating rather than burying. The migration guide's `ms.date`
is recent, and its body is a 2022 document with a refreshed stamp: it still tells
readers to "Apply to the new program upon receiving the email invite as part of the
beta launch by December 2022". These two restrictions have no second source anywhere.
The 500 and 100 call figures on the same page do, so they stand. Treat the webhook and
`BATCH_GET` restrictions as plausible and single-sourced, and confirm them in the
portal before you plan a build around either.

### Cost

**No price is published.** The product catalog page for the Community Management API
(<https://developer.linkedin.com/product-catalog/marketing/community-management-api>)
lists eligibility and no fee schedule, and no pricing or metering page was found on any
LinkedIn property. Access is gated by approval rather than by payment as far as these
sources show, which is an absence of evidence rather than a promise. LinkedIn nowhere
says this is free.

## Policy

Not legal advice. `docs/platform-policy.md` says the same thing at greater length and
maps this project's safety properties to the clauses they exist for. The clauses below
were read on 2026-08-01 and every one of them carries its own revision date, which you
should check before relying on any of this.

### Which contract governs

Two documents apply in layers, and the one most people cite is the outer layer.

| Document | Revised | Role |
|---|---|---|
| [Marketing API Terms](https://www.linkedin.com/legal/l/marketing-api-terms) | 2025-07-25 | The specific contract for the Community Management API. LinkedIn's own app review page and migration guide both open by telling applicants to read it, and the app review page's liability note names it twice |
| [API Terms of Use](https://www.linkedin.com/legal/l/api-terms-of-use) | 2022-12-13 | The general developer program terms underneath. The Marketing API Terms' own termination clause binds them together: "any termination of the API Terms of Use will automatically terminate these LMA Terms" |

Get this the right way round. A document that builds its whole compliance argument on
the API Terms of Use alone has skipped the contract LinkedIn routes Community
Management applicants to first.

### The sentence that reaches your model gateway

The Marketing API Terms carry a restriction on moving member data off the platform, and
it has no "sell" qualifier in front of it:

> "You must not however: (1) export, transfer, or distribute any Member Data (other
> than Lead Form Response Data or Page Messaging Data to Authorized Clients or their
> service providers) to any third party"

and the definition that pulls a comment into it:

> "For clarity, Member Data includes ... the content or information provided by the
> Member (e.g. a Member's post, comment, reaction, or message)"

commentdraft sends the text of every comment to whichever gateway `[model].base_url`
names, in the request `docs/architecture.md` describes. On LinkedIn that is a comment
by a member leaving LinkedIn's surface for a company that is not LinkedIn and is not
the operator. Whether that gateway is a "third party" or the operator's own service
provider is the question, and neither this page nor any source read for it can answer
it. Two things worth knowing while you take it to somebody who can:

- `[model].params.provider.data_collection = "deny"` is required on every model entry
  in this project and checked before the first call. It asks a gateway not to retain
  the text for training. It does not make a transfer not a transfer, and this clause is
  about the transfer.
- The API Terms of Use say a similar thing one layer down and more weakly, prohibiting
  a developer from moving Content to a third party under a longer list of verbs.

This is the single largest open question for a LinkedIn build, larger than the review
process, because it sits upstream of the design rather than in front of it. Settle it
before you spend twelve months in Development Tier. Whether Meta's Platform Terms say
something similar was not researched for `docs/platforms/facebook.md`, so read the
silence there as a gap rather than as an answer.

### "Automate posting"

Section 3.1 of the API Terms of Use is a list of prohibited developer actions and the
final item reads:

> "Use the Content or the APIs to automate posting on the LinkedIn Services."
>
> <https://www.linkedin.com/legal/l/api-terms-of-use>, revised 2022-12-13

Read on its own that sentence would forbid every programmatic `POST` to a comments
endpoint, including the ones LinkedIn ships scopes for. `w_organization_social_feed`
exists to "Post, comment, and react on posts on behalf of an organization", and the
Marketing API Terms affirmatively license a Marketing Application to manage Pages and
Member Profiles and to enable "an Authorized Client's Page or Member Profile to engage
with Members on the LinkedIn Services". LinkedIn cannot plausibly mean that no API may
ever create a comment while selling the permission to create comments.

The defensible reading is that "automate" means unattended posting with no specific
human decision behind each call, which is the shape commentdraft refuses to have: one
comment and one draft on screen, one keystroke, one send, no `--yes` and no `--all`.
`docs/platform-policy.md` maps that design to the consent clauses of two other
platforms. **LinkedIn's own text does not define "automate" here**, no clarifying
clause was found on any LinkedIn property, and the reading above is an argument rather
than a permission. A grep of the full Marketing API Terms found no automation clause,
no scheduling clause and no clause about unattended software of any kind, so this
sentence in the outer layer is the whole of the constraint. Take it to counsel before
you ship, and re-read the clause first: those terms are the older of the two documents
and could be revised without this page noticing.

### The member-facing rules

Section 8.2 of the User Agreement, "Don'ts", effective 2025-11-03, carries the
platform-wide clause on automated access. The whole of it, one bullet in a list opening
"You agree that you will not":

> "Use bots or other unauthorized automated methods to access the Services, add or
> download contacts, send or redirect messages, create, comment on, like, share, or
> re-share posts, or otherwise drive inauthentic engagement;"
>
> <https://www.linkedin.com/legal/user-agreement>

The clause turns on one adjective. The prohibition attaches to
**unauthorized** automated methods, and an app posting through the official versioned
API, on a token granted through a real consent screen, under a product LinkedIn itself
reviewed, is authorized by the plain meaning of that word. No sentence anywhere in
LinkedIn's public policy documents grants an explicit safe harbour to approved API use
with human sign-off, so this too is a reading.

The Professional Community Policies bear on the drafted text rather than on the
mechanism. The spam section entire, with LinkedIn's typographic apostrophes rendered as
ASCII and nothing else altered:

> "Do not spam members or the platform. We don't allow untargeted, irrelevant, obviously
> unwanted, unauthorized, inappropriate commercial or promotional, or gratuitously
> repetitive messages or similar content. Do not use our invitation feature to send
> promotional messages to people you don't know or to otherwise spam people. Please make
> the effort to create original, professional, relevant, and interesting content in order
> to gain engagement. Don't do things to artificially increase engagement with your
> content. Respond authentically to others' content and don't agree with others ahead of
> time to like or re-share each other's content."
>
> <https://www.linkedin.com/legal/professional-community-policies> (no revision date on
> the page)

Two sentences in there land on this design directly. "Gratuitously repetitive messages
or similar content" is what a batch of replies becomes when the same paragraph is sent
in twenty costumes, and `docs/limits.md` explains why repetition across a batch can be
reported here and not prevented. "Respond authentically to others' content" is the rule
a reviewer would read the drafts against. On LinkedIn, as on Meta, the platform-side
consequence is silent.

### What the data may be used for

The Restricted Use Cases page bounds the purpose as well as the transfer
(<https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2026-07>,
`ms.date: 2022-12-09`, portal-touched 2025-08-29, so read it as an old body under a
newer stamp):

> "Data Usage Limitations: Accessing, using, or storing member data for any use case
> other than to manage LinkedIn Pages or Profiles via your application is a violation
> of our Marketing API Terms. In particular, member data shouldn't be used for
> advertising, sales, or recruiting use cases..."

Reading comments on a Page you administer and publishing an approved reply to them sits
inside Page Management, which is LinkedIn's own named approved use case. Drafting a
reply that steers a commenter toward a product is closer to the sales edge of that
sentence than most operators will assume, and this tool exists to draft replies that
mention a product. Where your `[behavior]` call to action sits on that line is a
judgement about your own configuration, not something a connector could enforce.

One more, from the same page, for anyone tempted to build a shared inbox on top:

> "No Social Feeds: ... none of the data provided via our Community Management APIs can
> be used in a social feed use case (e.g. to display a feed of LinkedIn company updates
> on the company's website or intranet)."

A review page one operator opens on their own machine is not that. A hosted dashboard
several colleagues browse starts to be.

## What is still unknown

Every item here failed to resolve against a primary source, or cannot resolve without
credentials nobody involved has.

**Whether `r_member_social_feed` is granted to anyone who asks.** The permission is
documented as restricted and "granted to select developers only", the request path is
behind an authenticated portal, and nobody has walked it. LinkedIn publishes no
acceptance criteria for it beyond the Standard Tier list.

**Whether Development Tier includes programmatic refresh tokens.** The refresh token
page offers them to "all approved Marketing Developer Platform (MDP) partners" and
never says whether Development Tier approval is the approval it means. If it is not,
the first stage of the build re-authorizes by hand every 60 days.

**Whether webhooks and `BATCH_GET` are genuinely off during Development Tier.** Single
sourced, from a 2022 body under a 2026 stamp. Named in [Limits](#limits) rather than
smoothed into the prose above it.

**How long either review takes.** No SLA is published for Community Management on any
page read here. The "up to 30 business days" figure in circulation describes a
different program and was never confirmed against the primary page.

**The per-minute comment creation throttle.** The 429 exists and is quoted. The number
is on no page found, and the developer portal shows it only after you have already hit
the endpoint.

**Whether a password change invalidates a live token.** Neither the authorization code
flow page nor the refresh token page mentions it in either direction. Facebook
documents this explicitly, LinkedIn does not, and the absence is not an answer.

**Whether losing a tier revokes tokens already issued.** LinkedIn reserves a general
right to revoke at any time and ties it to nothing specific. No page connects app
review outcomes to live tokens.

**Whether sending comment text to a model gateway is a permitted use.** The clause is
quoted in full above. No interpretive guidance, FAQ or clarifying page was found on any
LinkedIn property, and the answer probably depends on the contract between the operator
and the gateway rather than on anything LinkedIn publishes.

**What the review actually asks a command line tool to demonstrate.** The screencast
shot list and the test-credentials requirement both describe an application a reviewer
signs into and clicks around. Nothing was found describing how a terminal tool with a
one-keystroke approval gate is expected to satisfy them, and this is the item most
likely to turn a technically finished build into a rejected submission.

# YouTube

Reading the comments on the videos your own channel published, and publishing one
approved reply at a time.

YouTube Data API v3. Every Google page cited below was fetched and read on
**2026-08-01**. Google stamps each developer page with a `Last updated` date in its
footer, and that date is given next to the link wherever it matters.

## What this gets you, and what it costs

**There is no YouTube connector.** commentdraft ships exactly one connector and it is
Facebook. Nothing in this repository holds a YouTube endpoint, a Google client id, an
OAuth flow, or a line of code that has ever spoken to `googleapis.com`. Naming YouTube
in a config is refused before a credential is asked for:

```
unknown platform: youtube. registered: facebook
```

`platform = "youtube"` does appear in `examples/field-guide-book/comments.csv`. That is
a column value which becomes one line of the model's prompt and selects nothing;
`docs/comments-csv.md` says so where the column is documented.

So this page documents how to get access and what the constraints are, for somebody
about to build the connector rather than somebody configuring one. Read
[What commentdraft would need](#what-commentdraft-would-need) for the shape of the
work.

The reason to read the rest of it is one clause. YouTube API Services Developer
Policies, section **III.E.3.d**, read 2026-08-01:

> "API Clients must clearly identify any actions that they take to insert, share,
> update, or delete data or content on the authorizing user's behalf. In addition, the
> user must expressly consent to those actions prior to their actual execution."
>
> <https://developers.google.com/youtube/terms/developer-policies> (Last updated
> 2026-06-24 UTC)

Consent has to be express, attached to "those actions" enumerated, and given "prior to
their actual execution". A person approving each reply immediately before it is sent is
what satisfies all three at once. On YouTube that is the only compliant shape for a tool
that posts comments, which means commentdraft's approval gate is a policy requirement
here rather than a product opinion. A batch approval, an approval column in a
spreadsheet, or a setting flipped once at install time does not satisfy it.
`docs/platform-policy.md` already maps this clause to `src/commentdraft/approve.py`.

What it costs:

| Cost | Where it lands |
|---|---|
| A keystroke per reply, permanently | III.E.3.d above. Not a limit anyone chose |
| 50 units per reply against a 10,000 unit day | 200 replies a day at the absolute ceiling, fewer once polling is subtracted. See [Limits](#limits) |
| No comment webhook of any kind exists | Polling is the only route, and polls spend the budget the replies come out of |
| `youtube.force-ssl` is the only scope that can post a reply | Its consent screen reads "See, edit, and permanently delete your YouTube videos, ratings, comments and captions". You cannot change that string |
| An app left in Testing gets a refresh token expiring in 7 days | Publishing the app fixes it, and publishing an external app with this scope is what starts OAuth verification |
| Comment text may be held for 30 calendar days | III.E.4.c. `comments.csv` and `review.csv` are both on that clock |
| Access for anyone but you needs OAuth verification | Published as "can take up to 10 days". More than 200 replies a day needs a separate YouTube compliance audit with no published turnaround at all |

Nothing here is billed. No pricing page and no metering documentation exists for the
YouTube Data API v3, on any of the quota, audit or verification pages read for this
document, and quota extensions are granted by review rather than sold. That is an
absence of a price rather than a promise of one.

## What is verified here, and what is not

**Nobody has made a single YouTube API call for this project.** There is no code to run
one with. Not one sentence below reports observed behaviour of the live API, and every
number on this page came off a Google page rather than out of a response body.

Verified by fetching the page and reading the raw HTML, 2026-08-01:

| What | How far the check went |
|---|---|
| Endpoint paths, HTTP methods, quota sentences | Read on the reference page for each method |
| The scope string and its consent-screen wording | Read on the OAuth 2.0 scopes page, character for character |
| Which methods carry an Authorization section and which do not | Counted in the raw HTML of all five comment methods |
| Error details | Read on the errors reference and on the reference page of each method, which do not always agree, and both are quoted where they differ |
| Policy clause numbers | The policy renders its numbering with CSS counters, so the letters are absent from the page text. The positions were derived twice from the raw HTML, independently, and cross-checked against the document's own internal references |
| Quoted policy and form text | Quoted verbatim from the page named beside it, with the date read |
| The compliance audit form | The live form was fetched and its field labels read, not summarised from a help page |

Not verified, and this list is complete:

- Whether a delegated Manager or Editor on a channel can authorise `comments.insert` at
  all. See [Channel roles](#channel-roles-and-brand-accounts).
- Whether the Google account chooser lists Brand Account channels during consent for
  this API.
- Whether `comments.insert` costs 50 units or 52. Google's own page states both. See
  [The 50 or 52 question](#the-50-or-52-question).
- Whether `youtube.force-ssl` is formally classified sensitive. It is provably not
  restricted; the sensitive label is asserted by the Cloud Console at the moment you add
  the scope, and Google publishes no enumerated list.
- Which scope satisfies the "properly authorized request" that `moderationStatus`
  requires. `force-ssl` certainly does. Whether `youtube.readonly` also would is not
  stated anywhere.
- Whether a reply posted through the API can be held by the channel's own comment
  moderation settings, and what the API returns if it is.
- The maximum comment length. The error exists; the number is unpublished.
- How long a YouTube compliance audit takes. No SLA is published.

Anything that could not be established at all is under
[What is still unknown](#what-is-still-unknown) rather than smoothed into the prose
above it.

## Before you start

| You need | You do not need |
|---|---|
| A YouTube channel, of any kind. No monetization requirement, no partner programme membership, no linked business account | A registered company |
| A Google account **merged with** that YouTube account. An unmerged account reads fine and fails only on write | A Google Workspace account |
| A Google Cloud project, one per client, created by you | A paid Cloud billing account |
| A domain you own, verified in Search Console, hosting a homepage and a privacy policy, **if** anyone other than you will use the app | A domain, if you are the only user and stay under 100 |
| Python 3 and commentdraft installed | A public HTTPS callback endpoint. There is no webhook to receive |

Read the first row twice, because several platforms do not work this way. Nothing about
the channel converts or changes by connecting it, so nothing about the channel is at
risk in connecting it. The two things that actually refuse a write are account state
rather than account type, and both are 403s:

> `ineligibleAccount`: "The YouTube account used to authorize the API request must be
> merged with the user's Google account to insert a comment or comment thread."
>
> <https://developers.google.com/youtube/v3/docs/comments/insert> (Last updated
> 2026-06-01 UTC)

> `authenticatedUserNotChannel`: "For this request the authenticated user must resolve
> to a channel, but does not."
>
> <https://developers.google.com/youtube/v3/docs/errors> (Last updated 2026-06-01 UTC)

### Channel roles and Brand Accounts

A Brand Account is "a Google account for your business or brand that's available for
some Google services. If your YouTube channel is linked to a Brand Account, multiple
people can manage it from their Google Accounts."
(<https://support.google.com/youtube/answer/9367690>)

Google's channel permissions table lists the roles as Owner, Manager, Editor, Editor
(Limited), Subtitle Editor, Viewer and Viewer (Limited)
(<https://support.google.com/youtube/answer/9481328>). The row that looks like the
answer to "can a Manager authorise this" is titled "Reply to comments as the channel
**from YouTube Studio**", and the whole table is scoped to three columns which are
Studio on a computer, the Studio app, and YouTube. The Data API is not one of them. The
same page warns that "Some actions may not be available at all when acting as a
delegate."

**Assume only the channel owner can authorise this until somebody tests it.** Nothing in
the Data API documentation says a delegated Manager or Editor can authorise a
`comments.insert` for a channel they do not own, and the one error that sounds relevant,
`accountDelegationForbidden`, is documented against the `onBehalfOfContentOwner`
parameter, which is a content-partner feature rather than channel permissions. The test
is two consents: an owner account, then a Manager-only account, against a throwaway
video. Twenty minutes settles it and nobody has spent them.

Service accounts do not work at all, so there is no way around this with a headless
credential:

> "The OAuth 2.0 flow for service account flow supports server-to-server interactions
> that do not access user information. However, the YouTube Data API does not support
> this flow. Since there is no way to link a Service Account to a YouTube account,
> attempts to authorize requests with this flow will generate a NoLinkedYouTubeAccount
> error."
>
> <https://developers.google.com/youtube/v3/guides/authentication> (Last updated
> 2026-06-01 UTC)

Every deployment holds a user refresh token obtained through an interactive consent by a
human being, and there is no second route.

## Getting a token

Steps 1 through 9 get you posting to your own channel. Steps 10 through 13 are what you
need before the token stops dying weekly and before anyone else can use the app. Step 14
is only if 200 replies a day is not enough.

1. Create a Google Cloud project at <https://console.cloud.google.com/>. Create one, not
   a shared one, and do not reuse a project you already have:

   > "If your API Client needs to create API Credentials to access or use YouTube API
   > Services, you must create exactly one (1) API Project for that API Client. Those API
   > Credentials are intended to be used exclusively by the associated API Client, which
   > means that you must not use that one (1) API Project for multiple API Clients."
   >
   > Developer Policies III.D.1.c,
   > <https://developers.google.com/youtube/terms/developer-policies>

2. Enable the YouTube Data API v3 in that project, under APIs and Services, Library.

3. Fill in the Google Auth Platform branding page: app name, user support email,
   developer contact. Do **not** put the word YouTube in the app name. The audit form
   asks about it directly and states the rule:

   > "Note: Your app name must NOT contain the word 'YouTube' unless you have prior
   > written approval from YouTube."
   >
   > <https://support.google.com/youtube/contact/yt_api_form>, form fetched 2026-08-01

4. Leave the publishing status at **Testing** for now, and read
   [The seven day token](#the-seven-day-token) before you decide how long to leave it
   there. Testing costs you a refresh token that expires every week.

5. Declare exactly one scope on the Data Access page:

   ```
   https://www.googleapis.com/auth/youtube.force-ssl
   ```

   Nothing narrower can post a comment. The consent screen your operator will read says
   "See, edit, and permanently delete your YouTube videos, ratings, comments and
   captions" (<https://developers.google.com/identity/protocols/oauth2/scopes>, Last
   updated 2026-05-26 UTC). Warn them before they see it. Requesting a second scope is a
   policy problem rather than a convenience:

   > "API Clients must obtain user consent in accordance with the applicable laws and
   > only request access to authorization scopes that they currently use. [...] Do not
   > try to future-proof your access to data by asking for permissions that would enable
   > features that you have not yet built."
   >
   > Developer Policies III.D.2.a.ii

6. Create an OAuth client ID of type **Desktop app**. Use a loopback redirect. Google's
   own sample is `redirect_uri=http%3A//127.0.0.1%3A9004`
   (<https://developers.google.com/youtube/v3/guides/auth/installed-apps>, Last updated
   2026-05-26 UTC). The out-of-band flow that older YouTube CLI tutorials all use is
   gone:

   > "The redirect_uri parameter may refer to the OAuth out-of-band (OOB) flow that has
   > been deprecated and is no longer supported."
   >
   > same page

   `urn:ietf:wg:oauth:2.0:oob` gets you `redirect_uri_mismatch` and an afternoon.

7. Add yourself as a test user while the app is in Testing.

8. Run the installed-app OAuth flow: generate the PKCE verifier and challenge, send the
   authorization request, consent, exchange the code. Store the refresh token. It will be
   there:

   > "Note that refresh tokens are always returned for installed applications."
   >
   > same page

9. Put the refresh token, the client id and the client secret in environment variables,
   in a `.env` file next to `config.toml`, never in `config.toml` itself. The client
   secret in particular cannot go anywhere a repository can reach:

   > "you must not share or disclose your API Credentials to any other third party, allow
   > access to or use of your API Credentials by any other third party, or embed your API
   > Credentials in open source projects."
   >
   > Developer Policies III.D.1.d

   commentdraft is Apache-2.0 and public. Each operator registers their own Cloud project
   and holds their own secret. Nothing shared could ever ship in this repository.

10. Verify ownership of the domain you list as your homepage, in Google Search Console:

    > "An account listed as a project owner or editor on your GCP account must verify
    > ownership of the authorized domain using Google Search Console."
    >
    > <https://support.google.com/cloud/answer/13464321>

11. Publish a homepage and a privacy policy on that domain. Google's stated requirements,
    verbatim from the same page: "The homepage must be hosted on a verified domain you
    own"; "The homepage must describe your app's functionality to its users. Your homepage
    can not be only a login page"; "The Privacy Policy should be hosted within the domain
    that hosts your homepage"; "The Privacy Policy must be linked from the OAuth consent
    screen on the Google API Console".

12. Record a demonstration video. The requirements are specific and a submission is
    rejected for missing any of them. From
    <https://support.google.com/cloud/answer/13464321>: it "Must show the end-to-end flow
    of your app including the OAuth grant process"; "Must show the same application you
    have submitted for verification (including app name, branding)"; "Show the complete
    OAuth Consent Screen"; "Please ensure the language setting on the bottom-left corner
    of the consent screen is toggled to 'English'". Upload it "to YouTube Studio and set
    its Visibility as Unlisted"
    (<https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification>,
    Last updated 2026-07-17 UTC).

13. Move the publishing status to In Production and submit for verification. Write the
    scope justification knowing what Google asks: "You must provide a detailed
    justification for your requested scope(s) which should include an explanation why
    narrower scopes would not work"
    (<https://support.google.com/cloud/answer/13464321>). The true answer is short. No
    narrower YouTube scope grants `comments.insert`, and the scope list on
    <https://developers.google.com/identity/protocols/oauth2/scopes> is where you can show
    that.

    > "The sensitive scope verification process can take up to 10 days to complete."
    >
    > <https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification>

14. Only if you need more than 10,000 units a day, submit the YouTube API Compliance
    Audit. See [The compliance audit](#the-compliance-audit).

### When you can skip steps 10 through 13

If you are the only user, you can run unverified. The cap counts people who have granted
consent. It says nothing about how many calls you make:

> "Personal Use apps: If the app is for your personal use (fewer than 100 users), you and
> your limited number of users can continue using the app without going through
> verification"
>
> "Note: Your app will be subject to the unverified app screen and the 100-user cap will
> be in effect when an app is in development/testing/staging. This cap is removed only
> after an app has been successfully verified."
>
> <https://support.google.com/cloud/answer/13464323>

Skipping verification and staying in Testing are two different decisions, and only the
first is free. Staying in Testing is what costs the seven day token.

## What commentdraft would need

The connector interface is two methods, in `src/commentdraft/platforms/__init__.py`:
`fetch_comments(config, since) -> list[dict]` and
`publish_reply(config, parent_id, text) -> str`. A YouTube connector is registered with
`@register("youtube")` and imported at the bottom of that module, exactly as
`facebook.py` is. What follows is the mapping, and the four places it does not fit.

### The calls

| What it is for | The call | Cost |
|---|---|---|
| The threads on a channel | `GET https://www.googleapis.com/youtube/v3/commentThreads` with `allThreadsRelatedToChannelId` | 1 unit per page |
| The rest of a thread's replies | `GET https://www.googleapis.com/youtube/v3/comments` with `parentId` | 1 unit per page, per thread that needs it |
| The held queue | the same `commentThreads.list` with `moderationStatus=heldForReview` | 1 unit per page |
| Video titles for `post_title` | `GET https://www.googleapis.com/youtube/v3/videos` with a comma-separated `id` list | 1 unit per call |
| One reply | `POST https://www.googleapis.com/youtube/v3/comments` with `part=snippet` | 50 units, or 52. See [The 50 or 52 question](#the-50-or-52-question) |
| A read-back after a write | `GET https://www.googleapis.com/youtube/v3/comments` with `id` | 1 unit |
| Approving a held comment | `POST https://www.googleapis.com/youtube/v3/comments/setModerationStatus` | 50 units |

Sources, all read 2026-08-01:
<https://developers.google.com/youtube/v3/docs/commentThreads/list>,
<https://developers.google.com/youtube/v3/docs/comments/list>,
<https://developers.google.com/youtube/v3/docs/comments/insert>,
<https://developers.google.com/youtube/v3/docs/videos/list>,
<https://developers.google.com/youtube/v3/docs/comments/setModerationStatus>,
<https://developers.google.com/youtube/v3/determine_quota_cost>.

There is no `channelId` filter, whatever the implementation guide says. See
[Google's own guide is wrong about channelId](#googles-own-guide-is-wrong-about-channelid).

### The row shape, and where it does not fit

`fetch_comments` returns rows in `engine.IN_FIELDS` shape, which is exactly `id`,
`platform`, `author`, `comment`, `post_title`, and a sixth key is a column nothing
downstream has a meaning for.

| Column | Where it comes from | The catch |
|---|---|---|
| `id` | `comment.id` | Fine |
| `platform` | the literal `youtube` | Fine |
| `author` | `snippet.authorDisplayName` | Fine, and optional. `docs/comments-csv.md` explains why an absent author is left absent |
| `comment` | `snippet.textDisplay`, with `textFormat=plainText` | Not the raw text. See below |
| `post_title` | `commentThread.snippet.videoId`, then a `videos.list` call | The `comment` resource carries no `videoId` at all. The title costs a second call |

**The comment text you get is not the comment text that was typed.** `snippet.textOriginal`
is described as "The original, raw text of the comment as it was initially posted or last
updated. The original text is only returned to the authenticated user if they are the
comment's author." A channel owner reading a viewer's comment is not that comment's
author, so the field is withheld and `textDisplay` is what you have. Google on what
`textDisplay` is:

> "The comment's text. The text can be retrieved in either plain text or HTML. (The
> comments.list and commentThreads.list methods both support a textFormat parameter,
> which specifies the chosen text format.) Even the plain text may differ from the
> original comment text. For example, it may replace video links with video titles."
>
> <https://developers.google.com/youtube/v3/docs/comments> (Last updated 2026-06-01 UTC)

Two consequences. Set `textFormat=plainText` on every read, because the default is `html`
(<https://developers.google.com/youtube/v3/docs/commentThreads/list>) and HTML entities in
a prompt are a defect nobody notices until a reply quotes one back. And accept that the
text a person approves a reply to has been rewritten by YouTube before you saw it, which
is a fact worth putting in front of the reviewer rather than in a connector comment.

### Four things the Facebook connector does that this one cannot copy

**The parent id is not the id of the comment being answered.** `snippet.parentId` on an
inserted reply must be the top-level comment's id, which is the same string as the
`commentThread` id
(<https://developers.google.com/youtube/v3/guides/implementation/comments>). YouTube
supports "replies only for top-level comments"
(<https://developers.google.com/youtube/v3/docs/comments/list>), so a reviewer answering
somebody three levels down gets a reply at the bottom of the thread addressed to nobody.
The Facebook connector drops any comment carrying a `parent` for the same reason and says
so on the page for that connector. The same rule applies here and for a stronger reason:
Facebook flattens threads, YouTube refuses them.

**`canReply` has to be checked before a draft is written, not before a send.**
`commentThread.snippet.canReply` is "This setting indicates whether the current viewer can
reply to the thread" (<https://developers.google.com/youtube/v3/docs/commentThreads>). The
error you get otherwise is a 400 that names the field: `operationNotSupported`, "The API
user is not able to insert a comment in reply to the top-level comment identified by the
snippet.parentId property. In a commentThread resource, the snippet.canReply property
indicates whether the current viewer can reply to the thread."
(<https://developers.google.com/youtube/v3/docs/comments/insert>). Learning that at the
send costs 50 units and a reviewer's keystroke. Learning it at the pull costs nothing.

**`--since` has no server-side counterpart worth using.** `commentThreads.list` has no
`publishedAfter` parameter; the filters are `allThreadsRelatedToChannelId`, `id` and
`videoId`, and `order` takes `time` or `relevance` only. So `--since` stays what it is for
Facebook: applied after the fetch, on our side, narrowing what reaches the CSV and
reducing no API call. `docs/configuration.md` documents that behaviour as the connector's
to define.

**The write check has less to prove and still needs one.** Facebook's connector reads back
every write because Meta documents one endpoint as two incompatible operations.
`comments.insert` has no such ambiguity: it is documented as "Creates a reply to an
existing comment" and nothing else. What a read-back would prove here is different and
still worth 1 unit: that the reply is visible at all. See
[A held reply and a live reply look identical](#a-held-reply-and-a-live-reply-look-identical).

### The config

The tables would be the ones that already exist. `[source]` for reading, `[publish]` for
writing, both optional, and a config with `[source]` and no `[publish]` is a read only
deployment that cannot send anything because there is no write credential anywhere for it
to reach. `docs/configuration.md` is the reference.

```toml
[source]
platform = "youtube"
credential_env = "YOUTUBE_REFRESH_TOKEN"
```

That is refused today, by name, and will stay refused until somebody writes the connector.
A YouTube connector would need to declare its own extra keys through `SOURCE_KEYS` and
`PUBLISH_KEYS` so the config vocabulary freeze in `tests/test_guarantees.py` can see them:
the channel id at minimum, and the client id and client secret as further `*_env` names,
because a refresh token alone cannot mint an access token.

Nothing in the approval gate changes. `src/commentdraft/approve.py` already does what
III.E.3.d requires, and `tests/test_guarantees.py` walks the AST of every module to keep
it that way.

## Policy, which is what decides the shape of this

Source for everything in this section:
<https://developers.google.com/youtube/terms/developer-policies>, Last updated
2026-06-24 UTC, fetched and read 2026-08-01.

Clause numbering note, because the numbers matter and the page hides them. The policy
renders its list numbering with CSS counters, so no letter appears in the page text. The
positions below were derived from the raw HTML by walking `<ol>`, `<ul>` and `<li>`
nesting and each list's `list-style-type`, twice and independently, and checked against
the document's own internal cross-references, which use exactly this scheme and cite
`III.A.2.i`, `III.D.1.c`, `III.E.4.b`, `III.E.4.c` and `III.G.1.d` among others. Two
traps. Under III.D.2 the three "For example" bullets about the IFrame Player, Data API
and Analytics API sit in a plain `<ul>` and carry no letter; counting them as a, b and c
puts everything after them out by three. And III.D.3, III.D.4 and III.D.7 are unlettered
prose with no sub-list at all, so they can be cited only at subsection level.

### III.E.3.d, and the clause that pairs with it

III.E.3.d is quoted in full at the top of this page. It sits under "Authorized Data
Usage", whose own scope statement names this use case:

> "They are relevant for any API Client that writes data via an API request [...] For
> example, these policies apply to any API Client that enables a user to upload videos,
> retrieve the user's list of uploaded videos, create playlists, or comment on videos."

Section III.I opens "You and your API Clients must not, and must not encourage, enable, or
require others to:" and its second item is:

> "misuse YouTube API Services or engage in abusive behaviors related to those Services.
> For example, you must not automate or trigger views, uploads, comments, likes,
> dislikes, or other actions without the user's prior specific and express consent;"

Read the conditional rather than the verb. What III.I.2 forbids is automating a comment
**without** prior specific express consent. Consent is the hinge, and III.E.3.d is what
says what that consent has to look like: express, enumerated, and prior to execution.
Read together, the two clauses specify a design, and the design they specify is one
reply in front of one person immediately before the call that sends it.

Three further obligations the same design has to carry, which are separate requirements
rather than restatements:

1. III.E.3.d's first sentence is its own rule. The approval screen has to state plainly
   that the keystroke posts a public reply to YouTube as the operator's channel.
2. III.E.3.e: "API Clients must clearly identify the YouTube channel or content owner that
   is associated with any request that requires user authorization." The screen has to name
   which channel the reply goes out as.
3. III.D.2.b.i: "API Clients must clearly and accurately identify to the user the entity or
   product that is requesting access to user data and the reason for requesting that
   access". And III.D.2.b.iii: "Users should not be surprised to learn that an API Client
   contains hidden features, services, or actions that are inconsistent with the Client's
   marketed purposes."

The other clauses in the III.E.3 list, which apply in full: III.E.3.a on being honest about
what data is collected and why; III.E.3.b, "API Clients must not display or allow access to
Authorized Data to anyone other than the authorizing user or agents expressly approved by
that user"; III.E.3.c on staying inside the privacy policy and the consent obtained.

### Retention: 30 days, and 7 days on request

> "API Clients may store all other types of Authorized Data not identified in section
> (III.E.4.b) for as long as is necessary for the purposes of the specific consent granted
> by an active user and for no longer than 30 calendar days. After 30 calendar days, the
> API Client must either delete or refresh the stored data."
>
> III.E.4.c

Comment text is "other types". A `comments.csv`, a `review.csv`, a `pull-state.json` full
of ids and an `out/` directory are all storage of Authorized Data, and 30 days is the
ceiling on each of them. III.E.4.d applies the same 30 days to Non-Authorized Data.
III.E.4.g adds a deletion obligation on request: "you must then delete it as soon as
possible and within 7 calendar days."

commentdraft holds none of this for you. It writes CSVs where you point it and never
deletes one. `docs/platform-policy.md` says the same thing from the other side: retention is
your policy to set and not a feature this tool has. On YouTube it is also a clause with a
number.

### Revocation

> "Every API Client must provide a clearly explained and easy way for users to revoke any
> authorization consent they have provided to an API Client to access YouTube API
> Services."
>
> "When a user revokes consent through this mechanism, the API Client must programmatically
> revoke that token right away to communicate the change in permissions to Google."
>
> "following revocation of consent through this mechanism, you and your API Clients must
> delete all Authorized Data that was accessed or stored pursuant to that consent. That
> deletion should happen as soon as possible and must take place within 7 calendar days of
> the revocation."
>
> III.D.2.c.i

For a single-operator command line tool the authorizing user and the operator are the same
person, which makes this cheap to satisfy and easy to forget entirely. It is a build item
for the connector: a way to revoke, and a delete that follows it.

### Scraping is out, which is why polling is the only route

III.E.6: "You and your API Clients must not, and must not encourage, enable, or require
others to, directly or indirectly, scrape YouTube Applications or Google Applications, or
obtain scraped YouTube data or content." III.I.14 forbids using "any technology other than
YouTube API Services to access or retrieve API Data". III.D.7 adds "You must not use
undocumented APIs without express permission."

With no comment webhook in existence, polling the documented endpoints is the whole of the
compliant surface. Every route around the polling cost is closed by one of those three
clauses.

### Ninety days of inactivity

> "YouTube reserves the right to disable or curtail your access to, or use of, specific
> YouTube API Services if your API Project has been inactive for 90 consecutive days."
>
> III.D.4

commentdraft is used in bursts by design, so this is a real exposure rather than a
theoretical one. An operator who answers a batch of comments in March and comes back in
July may find the project curtailed with nothing changed anywhere. The Facebook connector
has a trap at the same interval for a different reason, which is a coincidence worth
knowing about rather than a shared mechanism.

### Child-directed clients cannot write at all

From the API Services Terms of Service, section "Known Child-Directed API Client": "no
YouTube API Services write-based actions (such as, but not limited to, uploading content,
commenting and creating/sharing playlists) taken by users of Known Child-Directed API
Client will be implemented on YouTube websites, applications, services and products"
(<https://developers.google.com/youtube/terms/api-services-terms-of-service>).

### No clause requires you to label a machine-drafted reply

Not in these policies. The full policy text was searched for the vocabulary such a clause
would use and no requirement to label automated or machine-generated comment text exists in
the YouTube API Services Developer Policies. Two clauses come close enough to be mistaken
for it, and neither says it:

> III.I.11: "confuse, deceive, defraud, mislead, misrepresent, defame, abuse, stalk,
> threaten, spam, surprise, or harass anyone;"

> III.E.4.h, second sentence: "To the extent your API Clients display any information, data
> or metrics not based on API Data alongside API Data, your API Clients must include a clear
> and prominent disclosure there that such information, data and metrics are not from
> YouTube and are part of your own product."

III.E.4.h is about what your own interface displays next to YouTube data, not about the text
of a comment you post. YouTube's product-side synthetic media rules exist and are about
videos rather than comments.

Absence of a found clause is not proof of absence, and it is also not permission from
anywhere else. commentdraft requires `[behavior].bot_disclosure_text` and renders it
verbatim into the prefix with no setting that turns it off, for reasons that are about the
EU AI Act rather than about YouTube. `docs/platform-policy.md` has the mapping.

### III.E.4.h's first sentence, which nobody has resolved

> "Your API Clients must not (i) replace API Data with similar, independently calculated
> data, or (ii) access or use API Data to create new or derived data or metrics."

Whether a reply drafted from a customer's comment is "derived data" under clause (ii) is not
obvious. Every surrounding example in III.E.4 is about metrics, likes and view counts, which
argues that it is not. Nothing in the clause says so. This is listed here rather than
resolved, and it is listed at all because a page that walks III.E clause by clause and skips
this one is a page that quietly decided something.

## What breaks, and what each failure means

### The seven day token

The single most common "it worked for a week and then died" report for any Google API, and
it applies here in full.

> "A Google Cloud Platform project with an OAuth consent screen configured for an external
> user type and a publishing status of 'Testing' is issued a refresh token expiring in 7
> days, unless the only OAuth scopes requested are a subset of name, email address, and user
> profile (through the userinfo.email, userinfo.profile, openid scopes, or their OpenID
> Connect equivalents)."
>
> <https://developers.google.com/identity/protocols/oauth2>

`youtube.force-ssl` is not in that exempt subset. An app left in Testing stops working every
seventh day, with an `invalid_grant`, silently, on a schedule nobody set. The fix is moving
the publishing status to In Production, which for an external app with a sensitive scope is
what starts OAuth verification. That is the whole reason to publish an app you never intend
anyone else to use.

A published app's refresh token stops working for these reasons and no others:

> "The user has revoked your app's access."
> "The refresh token has not been used for six months."
> "The user changed passwords and the refresh token contains Gmail scopes."
> "The user account has exceeded a maximum number of granted (live) refresh tokens."
> "The user granted time-based access to your app and the access expired."
> "If an admin set any of the services requested in your app's scopes to Restricted (the
> error is admin_policy_enforced)."
> "For Google Cloud Platform APIs - the session length set by the admin could have been
> exceeded."
>
> same page

Read the third one carefully before repeating it. **A password change does not kill a
YouTube-scoped token.** The clause is conditioned on the token containing Gmail scopes, and
`youtube.force-ssl` is not one. Facebook behaves the opposite way and has a subcode for it,
which is exactly how this gets repeated wrongly.

One more from the same page, for an operator authorising several machines:

> "There is currently a limit of 100 refresh tokens per Google Account per OAuth 2.0 client
> ID. If the limit is reached, creating a new refresh token automatically invalidates the
> oldest refresh token without warning."

### The held queue is invisible by default

For a tool whose job is triage this is the most expensive silent default on the platform.

`commentThreads.list` takes `moderationStatus`, and the page states its default plainly:
"The default value is published." A connector that never sets the parameter never sees a
single held comment, with no error and no warning, while the queue fills up in Studio.

| Value | What the page says it returns |
|---|---|
| `heldForReview` | "Retrieve comment threads that are awaiting review by a moderator. A comment thread can be included in the response if the top-level comment or at least one of the replies to that comment are awaiting review." |
| `likelySpam` | "Retrieve comment threads classified as likely to be spam. A comment thread can be included in the response if the top-level comment or at least one of the replies to that comment is considered likely to be spam." |
| `published` | "Retrieve threads of published comments. This is the default value. A comment thread can be included in the response if its top-level comment has been published." |

<https://developers.google.com/youtube/v3/docs/commentThreads/list>, Last updated
2026-06-01 UTC.

Three things about that parameter. It "can only be used in a properly authorized request",
and the page names no scope anywhere, which is why the exact scope is in
[What is still unknown](#what-is-still-unknown). It "is not supported for use in conjunction
with the id parameter". And there is no `rejected` value on the filter, although the
`comment` resource's own `snippet.moderationStatus` field lists four valid values including
`rejected` (<https://developers.google.com/youtube/v3/docs/comments>). You can read that a
comment was rejected. You cannot ask for the rejected ones.

The per-comment field carries the same authorisation condition:

> "snippet.moderationStatus [...] This property is only returned if the API request was
> authorized by the owner of the channel or the video on which the requested comments were
> made. Also, this property isn't set if the API request used the id filter parameter."
>
> same page

So an unauthorised read gives you published comments and no moderation metadata at all; an
owner-authorised read gives you the held queue and the status field. Approving a held comment
is `comments.setModerationStatus` at 50 units, "authorized by the owner of the channel or
video associated with the comments"
(<https://developers.google.com/youtube/v3/docs/comments/setModerationStatus>).

Held comments do not wait forever:

> "Comments held are: Kept in YouTube Studio for up to 60 days."
>
> <https://support.google.com/youtube/answer/9483359>

A tool that is the operator's only view of that queue and that goes down for two months has
lost the backlog permanently, and nothing anywhere reports it.

### A held reply and a live reply look identical

Undocumented, and worth a build decision anyway. YouTube's comment moderation settings
include "Hold all: Hold all comments"
(<https://support.google.com/youtube/answer/9483359>). Whether a channel owner's own reply,
posted through the API, is exempt from the channel's own hold setting is not stated on that
page, on `comments.insert`, or in the errors reference. Nothing was found in either
direction.

The failure mode is what makes it worth naming. A held reply returns a 200 with a comment
resource in the body, exactly like a published one. The reviewer is told the reply went out
and the customer never sees it, and nothing in the tool or the response body says so. One
`comments.list` read-back at 1 unit against a keystroke costs nothing anybody can measure
and is the only thing that could tell the two apart, if the moderation status is even
returned on a freshly inserted comment, which is itself unverified.

### Google's own guide is wrong about channelId

<https://developers.google.com/youtube/v3/guides/implementation/comments> still says: "To
retrieve comments about a channel, follow the instructions for retrieving comments for a
video. However, instead of setting the videoId parameter, set the channelId parameter".

There is no `channelId` filter. The current reference page lists exactly three, and only one
of them may be set per request: `allThreadsRelatedToChannelId`, `id`, `videoId`
(<https://developers.google.com/youtube/v3/docs/commentThreads/list>). This is almost
certainly fallout from the April 30 2024 changelog entry recording that "The API no longer
supports the ability to insert or retrieve channel discussions"
(<https://developers.google.com/youtube/v3/revision_history>). Follow the guide and you get
an `invalidFilters` or `unexpectedParameter` error and lose an afternoon. Use
`allThreadsRelatedToChannelId`.

### A thread does not carry all its replies

> "The list contains a limited number of replies, and unless the number of items in the list
> equals the value of the snippet.totalReplyCount property, the list of replies is only a
> subset of the total number of replies available for the top-level comment. To retrieve all
> of the replies for the top-level comment, you need to call the comments.list method and use
> the parentId request parameter to identify the comment for which you want to retrieve
> replies."
>
> <https://developers.google.com/youtube/v3/docs/commentThreads> (Last updated 2026-06-01 UTC)

A connector that treats `replies.comments` as complete shows the reviewer partial
conversations and drafts replies duplicating one the operator already posted. Compare
`replies.comments` length against `snippet.totalReplyCount` on every thread and follow up
where they differ. Each follow-up is 1 unit and they add up on a busy channel.

### The error table

Every row below is quoted from the page named under it. The errors reference and the
method's own reference page carry different text for several of these details, because the
errors reference covers `comments.insert` and `commentThreads.insert` in separate sections
with different property paths. The wording below is the one on the method page for the call
a connector would make, which is `comments.insert`.

| HTTP | Detail | What the page says | What you do |
|---|---|---|---|
| 400 | `commentTextRequired` | "The comment resource that is being inserted must specify a value for the snippet.textOriginal property. Comments cannot be empty." | An empty draft reached the send. `commentdraft run` decides an empty comment locally as `skip`, so this is a connector defect |
| 400 | `commentTextTooLong` | "The comment resource that is being inserted contains too many characters in the snippet.textOriginal property." | The limit is unpublished. See [What is still unknown](#what-is-still-unknown) |
| 400 | `invalidCustomEmoji` | "The comment resource that is being inserted contains invalid custom emoji." | Strip it. The reply text came out of a model |
| 400 | `invalidCommentMetadata` | "The request metadata is invalid." | The request body shape is wrong |
| 400 | `operationNotSupported` | "The API user is not able to insert a comment in reply to the top-level comment identified by the snippet.parentId property. In a commentThread resource, the snippet.canReply property indicates whether the current viewer can reply to the thread." | Check `canReply` at the pull instead. This one costs 50 units to learn |
| 400 | `parentCommentIsPrivate` | "The specified parent comment is private. The API does not support replies to private comments." | Nothing to do. Skip the row |
| 400 | `parentIdMissing` | "The comment that is being inserted must be linked to a parent comment." | Connector defect |
| 400 | `processingFailure` | "While this can be a transient error, it usually indicates that the request's input is invalid." | Do not retry blindly. Every attempt costs quota |
| 403 | `forbidden` | "The comment cannot be created due to insufficient permissions. The request might not be properly authorized." | Scope or token |
| 403 | `ineligibleAccount` | "The YouTube account used to authorize the API request must be merged with the user's Google account to insert a comment or comment thread." | Not an auth bug. The human goes and merges the accounts on YouTube |
| 403 | `commentsDisabled` | "The video identified by the videoId parameter has disabled comments." | A normal state, not an error to retry |
| 403 | `authenticatedUserNotChannel` | "For this request the authenticated user must resolve to a channel, but does not." | The Google account has no channel |
| 403 | `quotaExceeded` | "The request cannot be completed because you have exceeded your quota." | Stop until midnight Pacific. See [Limits](#limits) |
| 404 | `parentCommentNotFound` | "The specified parent comment could not be found. Check the value of the snippet.parentId property in the request body to ensure that it is correct." | Usually a reply id passed where a top-level id belongs |

Sources: <https://developers.google.com/youtube/v3/docs/comments/insert> for the
insert-specific details and <https://developers.google.com/youtube/v3/docs/errors> for the
rest, both Last updated 2026-06-01 UTC. `ineligibleAccount` reads "Google account" on the
first page and "Google Account" on the second; nothing turns on the capital, and it is
mentioned because this page quotes rather than paraphrases.

### Retrying costs quota even when it fails

> "All API requests, including invalid requests, incur a quota cost of at least one point."
>
> <https://developers.google.com/youtube/v3/determine_quota_cost>

A retry loop against a 400 drains the budget the replies come out of. commentdraft's own
rule already covers the write path for a different reason: one keystroke has to mean at most
one POST, so the send never retries. The read path is where a naive backoff loop would do the
damage.

### Deprecated methods are still in the quota table

A row in the quota table is a price. It carries no claim that the method still exists.
`commentThreads.update` is listed at 50 units and was deprecated on July 2 2021: "The
commentThreads.update endpoint has been deprecated and is no longer supported."
`comments.markAsSpam` went the same way on September 12 2023 and
`brandingSettings.channel.moderateComments` on March 7 2024. All three from
<https://developers.google.com/youtube/v3/revision_history> (Last updated 2026-07-08 UTC).

### The quota page contradicts itself, and the wrong number is the one summarisers pick up

The body of <https://developers.google.com/youtube/v3/determine_quota_cost> carries this
sentence today: "The table shows that methods like videos.insert have the highest cost of
1600 points". The same page's own table and the December 4 2025 changelog entry both say the
video upload cost dropped "from approximately 1600 units to approximately 100 units". The
1600 figure is a stale auto-generated summary block sitting above the correct table, and it
is what any tool that summarises the page rather than parsing it will return. Read the table,
not the paragraph above it.

The same page is the reason to distrust any third-party guide asserting that `search.list`
costs 100 units. It costs 1 unit and is capped at 100 calls a day in a bucket of its own, and
has been since June 1 2026.

## Limits

`docs/limits.md` covers what commentdraft cannot do regardless of platform. This section is
what YouTube imposes.

### The daily quota, and what it makes the real reply ceiling

> "Projects that enable the YouTube Data API have a default quota allocation of 100
> search.list calls, 100 videos.insert calls, and 10,000 units per day combined for all other
> endpoints. You can see your quota usage on Quotas page in the Google API Console. Daily
> quotas reset at midnight Pacific Time (PT)."
>
> <https://developers.google.com/youtube/v3/determine_quota_cost> (Last updated 2026-06-01
> UTC)

Everything commentdraft would do comes out of that one 10,000 unit bucket. The costs, from
the same page's table:

| Resource | Method | Cost |
|---|---|---|
| commentThreads | list | 1 |
| comments | list | 1 |
| videos | list | 1 |
| channels | list | 1 |
| comments | insert | 50 |
| comments | update | 50 |
| comments | setModerationStatus | 50 |
| comments | delete | 50 |
| commentThreads | insert | 50 |

Reading is nearly free and writing is not. One unit buys up to 100 items, since `maxResults`
is "1 to 100, inclusive" with a default of 20, and each further page costs another unit:
"each request to retrieve an additional page of results incurs the estimated quota cost."

The arithmetic, with the ambiguity carried through rather than resolved. `comments.insert` is
documented at both 50 units and, for its `snippet` part, 2 more. Both figures are on the page
today. So every ceiling below has two values:

| Poll interval | Polling calls per day | Units left | Replies at 50 | Replies at 52 |
|---|---|---|---|---|
| never | 0 | 10,000 | 200 | 192 |
| hourly | 24 | 9,976 | 199 | 191 |
| every 15 minutes | 96 | 9,904 | 198 | 190 |
| every 5 minutes | 288 | 9,712 | 194 | 186 |
| every minute | 1,440 | 8,560 | 171 | 164 |

Those rows assume one page per poll and nothing else spent. Subtract further for each thread
whose replies have to be enumerated, each `videos.list` for a title, each read-back after a
write, each `setModerationStatus` at 50 units, and each failed request at 1 unit minimum. A
realistic figure for a channel busy enough to need this tool sits below every number in the
right-hand columns.

Two operational notes on the reset. It is midnight **Pacific**, not UTC and not local, so an
operator in Europe sees the budget refresh mid-morning, and one who schedules a nightly
catch-up at local midnight is running it eight or nine hours into the quota day. And the
quota is per Cloud project, not per channel and not per user: one project serving five
operators shares one 10,000 unit budget, which III.D.1.c forbids anyway.

### The 50 or 52 question

<https://developers.google.com/youtube/v3/docs/comments/insert> carries both of these
sentences today, verified in the raw HTML on 2026-08-01:

> "Quota impact: A call to this method has a quota cost of 50 units."

> "The part parameter identifies the properties that the API response will include. Set the
> parameter value to snippet. The snippet part has a quota cost of 2 units."

`part=snippet` is required on this method, so the two sentences describe the same call. The
quota table on the calculator page lists a flat 50. No current Google page reconciles them,
and none states whether a part cost is additive on top of a method cost or included in it.
The quota calculator, the full revision history and the getting-started overview were all
read looking for that rule and it is on none of them.

**Nobody knows whether a reply costs 50 units or 52.** The difference is eight replies a day
at the ceiling, 200 against 192, and it grows with every other call in the budget. Budget at
52, measure against the Quotas page in the Cloud Console on the first day, and treat any
figure derived from 50 as an upper bound until you have.

### Rate limits below a day

**Unpublished.** No per-second or per-minute limit for the YouTube Data API appears on the
quota calculator, the getting-started guide, or the quota and compliance audits page. Google's
generic Cloud tooling lets you cap your own usage per minute
(<https://support.google.com/googleapi/answer/7035610>) and mentions a `quotaUser` parameter,
but that is Google-wide plumbing rather than a YouTube limit. Assume an undocumented burst
limit exists and space requests anyway. Any specific queries-per-second number you find is
somebody's measurement, not a published figure.

### Webhooks

**There is no comment webhook.** YouTube's only push mechanism is PubSubHubbub, and its
complete event list is three items:

> "Your PubSubHubbub callback server receives Atom feed notifications when a channel does any
> of the following activities:" uploads a video, updates a video's title, updates a video's
> description.
>
> <https://developers.google.com/youtube/v3/guides/push_notifications> (Last updated
> 2026-06-01 UTC)

No comment event, no reply event, no moderation event. The hub is
`https://pubsubhubbub.appspot.com/subscribe` and the topic URL is
`https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID`, and neither is any use
here. Polling is the only option, scraping is prohibited by III.E.6 and III.I.14, and
undocumented endpoints are prohibited by III.D.7. Every poll spends the budget the replies
come out of, which is what makes the interval a real decision rather than a default.

### The compliance audit

Separate from Google OAuth verification, run by YouTube rather than by the Identity team, and
needed only for more than the default quota.

> "If your API Client reaches the quota limit for a service, you can apply for a quota
> extension by completing an API Compliance Audit where you must specify the use case for
> which you need the extension."
>
> Developer Policies III.D.3

The form is at <https://support.google.com/youtube/contact/yt_api_form>, appeals at
<https://support.google.com/youtube/contact/yt_api_appeals>, both linked from
<https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits> (Last updated
2026-06-24 UTC). The form was fetched and read on 2026-08-01.

An individual can apply. The applicant question offers "As an individual user", and the legal
name field says "If applying as an individual please write 'self'". A website is not optional
even then. "Your Organization's Primary Website" is a required field that "Must start with
https://", and so are "Primary Access URL", described as "Provide the main URL where we can
access your API Client (website, app store, login page)", and "Privacy Policy URL".

The uploads are the part that stops a command line tool. The form requires privacy policy
screenshots, a "Homepage Screenshot" that shows "where Privacy Policy link is located with
YouTube branding visible", and "Terms of Service Documentation", with OAuth consent screen
shots on top if the client uses OAuth, which this one does. A tool with no website cannot
complete this form as written. If an operator never needs more than the ceiling in the table
above, they never touch it. If they do, they need a real web presence first, and that is a
project to plan before promising anyone higher volume.

Two use-case categories on the form fit. "Tools for Creators" is described as "For
applications designed to help YouTubers grow their channel presence, manage comment replies,
or monitor earnings", and "Internal Company Tool" as "For proprietary tools exclusively
utilized by your organization's employees and not distributed or sold externally". The bar is
stated on the form itself: "Your application must comply with our developer policies including
demonstrating significant independent value to the YT ecosystem and its users. Applications
that are unable to meet requirements may not be granted additional quota."

Approval is not permanent. III.D.3 ties the grant to the approved use case and requires a
fresh audit when the use case changes, the form offers "Complete a compliance audit to keep
current quota (requested to complete re-audit)" as its own request type, and the audits page
notes periodic re-audits.

**No turnaround is published.** The audits page says only that "A member of YouTube's API
Services team will contact you as soon as possible." Do not build a launch date on any number
you have seen for this, and do not confuse it with the OAuth verification figure of up to 10
days, which is a different process run by a different team.

### Comment length

**Unpublished.** `commentTextTooLong` is documented and the number is not, on
`comments.insert`, `commentThreads.insert`, the comment resource, the errors reference or the
revision history. The widely repeated figure of 10,000 characters has no primary source.
`[behavior].max_reply_sentences` keeps drafts far below any plausible ceiling, so this matters
for the reviewer's edits rather than for the model's output.

## What is still unknown

Every item here failed to resolve against a primary source, or cannot resolve without a live
call. None of it is smoothed over above.

**Whether `comments.insert` costs 50 units or 52.** Both figures are on Google's own page.
See [The 50 or 52 question](#the-50-or-52-question). One day of real traffic measured against
the Cloud Console Quotas page settles it, and until somebody does that the reply ceiling is a
range rather than a number.

**Whether a delegated Manager or Editor can authorise a write.** Google documents delegated
channel permissions for YouTube Studio and says nothing about the Data API, and the one
error that sounds relevant belongs to a different feature. This decides whether a team can use
one connection or whether every channel needs its owner sitting at the keyboard, and it is
settled by two consents against a throwaway video.

**Whether the Google account chooser lists Brand Account channels during consent for this
API.** No Google page documenting the picker's behaviour for the YouTube Data API was found.
The auth guides, the registration guide, the errors reference and the Brand Account help page
were all read.

**Whether `youtube.force-ssl` is formally classified sensitive.** It is provably **not**
restricted: the enumerated restricted-scope list at
<https://support.google.com/cloud/answer/13464325> contains only Data Portability scopes on
the YouTube side and `force-ssl` is absent, so no annual third-party security assessment
applies. For sensitive, Google publishes no enumerated list. The classification is asserted by
the Cloud Console when you add the scope: "Scopes you specify are grouped into sensitive or
restricted categories to highlight any additional verification that's required"
(<https://support.google.com/cloud/answer/15549135>). The inference is strong, because the
scope grants delete rights over user content and the sensitive-scope page names "deleting a
YouTube video" as an example. It is still an inference, and a reader should confirm the label
in their own console before assuming the 10 day timeline applies to them.

**Which scope satisfies a "properly authorized request" for `moderationStatus`.**
`commentThreads.list` renders no Authorization section and names no scope anywhere, yet the
parameter requires authorisation. `youtube.force-ssl` certainly satisfies it, since
`setModerationStatus` requires exactly that scope, and a connector needs it for writing
regardless. Whether the narrower `youtube.readonly` would also work is unstated, which matters
because III.D.2 requires the narrowest scope. Do not claim `youtube.readonly` is sufficient
for the held queue.

**Whether a reply posted through the API can be held by the channel's own moderation
settings.** Nothing found in either direction. See
[A held reply and a live reply look identical](#a-held-reply-and-a-live-reply-look-identical).
This is the failure a reviewer is least equipped to notice, because the API's answer to a held
reply and to a published one is the same answer.

**Whether `snippet.moderationStatus` is even returned on a freshly inserted comment.** The
field is documented as returned only to the channel or video owner, which the operator is, and
nothing says whether an insert response carries it. If it does, the read-back above is one
call. If it does not, there is no cheap way to tell a held reply from a live one.

**Any per-second or per-minute rate limit.** Unpublished. See
[Rate limits below a day](#rate-limits-below-a-day).

**The maximum comment length.** Unpublished. See [Comment length](#comment-length).

**Pagination depth on `commentThreads.list`.** `nextPageToken` is documented and no maximum
result-set depth is. Whether a channel with hundreds of thousands of comments can be walked to
the end through `allThreadsRelatedToChannelId` is not stated on the reference page, the
pagination guide, the implementation guide or the revision history. A first pull against a
long-lived channel may not be a complete archive, and nothing would say so.

**How long a compliance audit takes.** No SLA is published anywhere. Treat it as unbounded.

**Whether a drafted reply is "derived data" under III.E.4.h(ii).** Unresolved, and the reason
it is unresolved is that the clause's surrounding examples are all metrics while its wording is
not limited to metrics. See
[III.E.4.h's first sentence](#iiie4hs-first-sentence-which-nobody-has-resolved).

**Whether any disclosure of software-assisted reply text is required by YouTube.** No such
clause was found in the Developer Policies or the API Services Terms of Service. Absence of a
found clause is not proof of absence. The replies are your own words, published under your own
channel, after your own approval, and `docs/platform-policy.md` covers the transparency rules
this project does build for. Operators in regulated sectors should take their own advice
rather than this page's.

# Reddit

Reading the comments under posts your own account submitted, and publishing one
approved reply at a time. What Reddit permits, what it makes you ask for first, and
how far a connector would still be from shippable.

Reddit Data API. Every Reddit-owned page cited below was fetched **live on
2026-08-01** with an ordinary browser User-Agent, not from an archive. Reddit's policy
documents carry their own effective and revision dates and those are given next to
each link. Reddit sets apostrophes and some dashes as typographic characters; quotes
here use the ASCII equivalents and are otherwise verbatim, and where a dash carried
meaning the substitution is named at the quote.

## What this gets you, and what it costs

**commentdraft has one connector and it is Facebook.** There is no Reddit connector.
Nothing under `src/commentdraft/platforms/` reads or writes Reddit, no subcommand
reaches reddit.com, and no configuration on this page can be made to run. Naming
Reddit in `[source]` or `[publish]` is refused before a credential is read:

```
$ commentdraft pull --config config.toml --out comments.csv
unknown platform: reddit. registered: facebook
$ echo $?
2
```

Observed against this repository on 2026-08-01. `commentdraft publish --config
config.toml --out out --dry-run` prints the same line and returns the same 2. This
page is what a Reddit connector would have to be built against, and a record of what
Reddit requires before one could run.

What Reddit permits is real. Reading a comment tree and posting a reply are both
first-party documented calls, free at 100 queries per minute per OAuth client id, and
nothing in Reddit's published rules prohibits a design where a person approves one
reply at a time. Four things sit between that and a working setup, and all four are
load bearing.

| Cost | Where it lands |
|---|---|
| Access has to be requested and granted before the first call | The Responsible Builder Policy states approval is required, and the route in is a support ticket form. See [Getting access](#getting-access) |
| No turnaround is published | Reddit states no SLA for that request anywhere this page could find. You cannot plan a start date |
| Content deleted on Reddit must be deleted in your possession, with 48 hours the recommended routine | This is a constraint on caching comment text, which is exactly what drafting against a comment does. See [The 48 hour rule](#the-48-hour-rule) |
| Whether your use is commercial is Reddit's call, decided from what you write on the ticket | An author replying about a book they sell is not in Reddit's own examples and is arguably inside its clause. See [Commercial use](#commercial-use) |

A fifth cost is not Reddit's and belongs here anyway: most of what is publicly known
about Reddit tokens comes from a repository Reddit archived in 2017. Reddit's own
current wiki links to it under a staleness banner. See
[Getting a token](#getting-a-token).

Selling commentdraft itself, rather than using it, is a different question with a
clearer answer. "Services, research, or data access for fees" and "Subscription
services" are both on Reddit's own published list of commercial purposes, and that
list is in [Commercial use](#commercial-use).

## What is verified here, and what is not

**Nobody has run anything against Reddit.** No Reddit account was used, no app was
registered, no client id or secret exists, and no token was ever minted. Every
authenticated behaviour described below is documentation, not observation.

Verified against Reddit's live pages, fetched 2026-08-01:

| What | How far the check went |
|---|---|
| Scope strings | Read from `https://www.reddit.com/api/v1/scopes`, the canonical JSON endpoint. 30 keys returned, counted |
| Scope descriptions | Quoted character for character from the same JSON |
| Endpoint paths, methods and per-endpoint scope tags | Read on `https://www.reddit.com/dev/api/oauth`, Reddit's own generated reference |
| Rate limit figures and header names | Read on the Data API Wiki, article 16160319875092, edited 2026-05-11 |
| The approval requirement | Read on four Reddit-owned pages, listed in full under [Getting access](#getting-access) |
| The deletion obligation | Read on the Data API Wiki and cross-checked against Data API Terms 3.2 |
| Commercial-use examples | Read on help article 14945211791892, edited 2026-05-28 |
| Quoted policy text | Quoted verbatim from the page named beside it, with that page's own revision date |
| Rate limit headers on an unauthenticated call | Measured, three consecutive requests. Numbers in [Limits](#limits) |
| That an unregistered platform name is refused | Run against this repository. Output above |

Not verified, and this list is complete:

- That bearer tokens expire after one hour. Single-sourced to a repository Reddit
  archived in 2017.
- That `duration=permanent` yields a refresh token, that `refresh_token` renews, and
  that `revoke_token` exists at the path given. Same single source.
- That `https://oauth.reddit.com` is the host for authenticated calls. Same single
  source. An unauthenticated `GET` there returns 403, which proves the host answers
  and nothing else.
- That the web, installed and script app types are still the taxonomy the app
  creation form offers. Same single source, and `/prefs/apps` redirects to a login
  page, so nobody without an account can look.
- Whether the password grant works on an account with two factor authentication
  enabled.
- Which JSON field separates a comment reply from an actual private message in an
  inbox listing.
- Whether a comment removed by a subreddit's filter is visible through the API to the
  author of the post it sits under.
- Whether an authenticated response carries the same three rate limit headers an
  unauthenticated one does.
- How long the approval request takes, because Reddit publishes no figure.

Anything that could not be established at all is under
[What is still unknown](#what-is-still-unknown) rather than smoothed into the prose
above it.

## Before you start

| You need | You do not need |
|---|---|
| A Reddit account. The App Registration page states "You'll need a human Reddit account to register." | A business entity or a company registration |
| An approved access request. This is the part with no timeline | Any identity or business verification document |
| An app registered for a client id and secret | A public HTTPS endpoint. No webhooks exist |
| A developer profile, separately, for the App profile label | A Reddit "business" account tier. None gates the Data API |
| A User-Agent in Reddit's published format, which is a term rather than a courtesy | A moderator role on any subreddit |
| Python 3 and commentdraft installed, for everything that is not the Reddit half | A Devvit app, if the ticket route is granted |

Reddit steers developers to its own hosted platform before it discusses the Data API
at all:

> "Developers should use the Developer Platform ('Devvit') to build apps on Reddit."
>
> "If your use case is not supported by Devvit, file a ticket here."
>
> Responsible Builder Policy, edited 2026-06-05
> (<https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy>)

A command line tool that runs on your laptop, reads your own posts and sends a reply
your finger approved is not a Devvit app. That puts you on the second sentence, and
the ticket is the route.

## Getting access

The research this page was written from concluded that no review was required for a
personal script app. That is wrong, and it is the single largest correction on this
page. Four current Reddit-owned pages say access is granted rather than taken.

> "Approval is required: You must request access and get explicit approval before
> accessing any Reddit data through our API, and you must agree to comply with all
> applicable terms."
>
> Responsible Builder Policy, edited 2026-06-05, article 42728983564564

> "To use Reddit's Data API for non-commercial purposes, you need to sign-up here"
>
> "Developer Platform & Accessing Reddit Data", edited 2026-05-28, article
> 14945211791892. "here" is a support ticket form, not the app creation page

> "The information you provide about your use case and App during Reddit's App Review
> will determine your eligibility and approval for commercial (or non-commercial) use
> of Reddit's developer tools and services."
>
> Same article. App Review is the mechanism that decides non-commercial eligibility

> "You can use the Reddit Data API, subject to our Responsible Builder Policy,
> Developer Terms and Data API Terms. To request, please contact us here."
>
> Reddit Data API Wiki, edited 2026-05-11, article 16160319875092

Data API Terms 3.2 then restricts use "beyond your approved use case", which
presupposes one exists (<https://redditinc.com/policies/data-api-terms>, Effective
June 19, 2023, Last Revised July 20, 2026).

Developer Terms 3.1 does say review happens "at Reddit's discretion", and that
sentence is about *additional* review rather than a way out of the flat requirement
above:

> "You understand and agree that Reddit may require you to submit your App for
> Reddit's review and approval at Reddit's discretion ('App Review'), including prior
> to distributing it through the Developer Platform, after hitting API rate limits, or
> at any time at Reddit's sole discretion."
>
> <https://redditinc.com/policies/developer-terms>, Effective September 24, 2024,
> Last Revised March 24, 2026

**No turnaround is published.** Reddit states no SLA for the access request, no
expected number of days, and no queue position. Any figure you have seen for it is
somebody's anecdote. Plan on the gate, not on a date.

The steps:

1. Read the Responsible Builder Policy end to end
   (<https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy>).
   It is short, it is the document the ticket is judged against, and its Enforcement
   section is where token revocation lives.

2. Decide which lane you are in before you open the form. The ticket form takes a
   type parameter and Reddit's own links preselect three different values:

   | Lane | Link Reddit publishes |
   |---|---|
   | Developer, non-commercial | `.../requests/new?ticket_form_id=14868593862164&tf_42139884615700=api_request_type_developer_clone` |
   | Commercial | `.../requests/new?ticket_form_id=14868593862164&tf_42139884615700=api_request_type_enterprise_clone` |
   | Research | `.../requests/new?ticket_form_id=14868593862164&tf_42139884615700=api_request_type_researcher_clone` |

   All three sit under `https://support.reddithelp.com/hc/en-us`. The bare form,
   `https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164`,
   is what the Data API Wiki's "contact us here" and the "sign-up here" link both
   point at. Which lane you pick is the commercial question below, and picking it is
   the first thing the form asks of you.

3. File the ticket, describing the use case accurately. "Be transparent" is a policy
   clause and not advice:

   > "Be transparent: You must not misrepresent or mask how or why you are accessing
   > Reddit data. This prohibits registering multiple accounts or submitting multiple
   > requests for the same use case."
   >
   > Responsible Builder Policy

   One request, one use case. Filing a second because the first is slow is the
   behaviour that sentence names.

4. Create the app for a client id and secret at
   <https://www.reddit.com/prefs/apps>. That URL returns HTTP 302 to
   `https://www.reddit.com/login/?dest=...` for anyone not signed in, observed
   2026-08-01, so the form cannot be previewed before you have an account.

5. Register the app for its profile label, which is a **different** surface from step
   4 and a separate requirement:

   > "Apps must register and create a developer profile to get an App profile label.
   > Apps must not circumvent any labeling performed by Reddit."
   >
   > Responsible Builder Policy, App Transparency

   The link behind "register" in that clause is
   <https://developers.reddit.com/app-registration>. That page, read 2026-08-01,
   describes itself as "Register your existing apps" and adds a date worth knowing
   before you plan anything:

   > "Apps that register by August 30, 2026, may be eligible to claim a $1,000 porting
   > bounty as part of Reddit's $1,000,000 Developer Platform App Migration Program."

   Twenty-nine days from the date on this page. Whether an app that does not exist yet
   can register is not stated, and the page requires a login before it says anything
   more, so nobody without an account can find out.

6. Choose an app type. The taxonomy is only documented on the archived repository, so
   read [Getting a token](#getting-a-token) before trusting it.

7. Set your User-Agent before the first call, in Reddit's format, because a default
   one is penalised on purpose. Format and example in
   [What breaks](#what-breaks-and-what-each-failure-means).

## Commercial use

This is the part a reader is most likely to get wrong, and it is unresolved.

Developer Terms 4.1, "Commercial Use Restrictions", prohibits without a separate
agreement:

> "access or use any of the Reddit Services and Data by or on behalf of a business or
> as part of a service or product that is monetized"
>
> <https://redditinc.com/policies/developer-terms>, Last Revised March 24, 2026

The same clause ends with a pointer that decides how broad it is:

> "For more information and examples of restricted commercial use, please review our
> Developer Documentation here."

Those examples are published, and they are specific:

> "We consider commercial purposes to include any use of our services by a business or
> on behalf of a business or as part of a monetized product or service. Some examples
> include but are not limited to: Mobile apps with ads, promos, or paywalls / Search
> or website ads / Services, research, or data access for fees / Subscription services
> / Sponsorships / Licensing or royalty fees for products / Free product features
> available for upsell / Publishing content from Reddit on monetized websites or apps
> with ads / Selling access to models trained on Reddit data"
>
> Article 14945211791892, edited 2026-05-28. The nine items are a bulleted list on
> Reddit's page and are run together here with slashes

Read the nine. Every one is about monetizing Reddit content, data or access:
displaying it next to ads, charging for it, licensing it, training on it. None of them
describes a person replying from their own account, under their own name, to comments
about a product they sell somewhere else.

The argument the other way is in the clause's own first sentence, which is broader
than its examples and says so: "any use of our services by a business or on behalf of
a business", and "include but are not limited to". An author who sells a book is a
business in most tax jurisdictions, and a reply that points at a purchase link is
promotion of a monetized product even though the product is not Reddit's data. Reddit
also states the default without qualification:

> "You cannot use any Reddit developer tools and services for commercial purposes
> without first getting our permission."
>
> Same article

**Nobody outside Reddit can settle this**, because the decision is Reddit's and it is
made from what you write on the ticket. Two things follow. Describe the use case
accurately on the form, including that you sell something, because the alternative is
the "Be transparent" clause. And if you reach the commercial lane, expect a contract
rather than a price list:

> "If you're interested in using Reddit data to power, augment, or enhance your product
> or service for any commercial purposes, you'll need our permission, and we'll require
> a contract."
>
> Same article

If what is being sold is commentdraft rather than the book, there is nothing to weigh.
"Services, research, or data access for fees" and "Subscription services" name that
directly, and no reading of the examples helps.

One adjacent door is closed outright, and readers reach for it by instinct:

> "No. The only official and authorized avenue for performing research using Reddit
> data is through the Reddit For Researchers (RFR) program. Using developer tools,
> APIs, or unauthorized third-party tools for academic research is a violation of our
> policies."
>
> Same article

Calling a pilot "research" to stay out of the commercial lane moves you into a program
with its own application and its own eligibility criteria.

## Getting a token

commentdraft ships no login helper for any platform, and would ship none for this one.
You perform the exchange yourself and put the result in an environment variable.

Everything in this section comes from `https://github.com/reddit-archive/reddit/wiki`,
a repository Reddit archived in 2017. Reddit still links to it and prints a warning
above the link:

> "Please note: Some of the information in our legacy API documentation and support
> resources may be out of date. Always consult our Developer Terms and Data API Terms
> for rules of use, terms, and conditions. Information linked from this page is for
> technical support guidance only."
>
> Reddit Data API Wiki, article 16160319875092, above its own links to that repository

That warning has a demonstrated instance. The archived page lists 19 scope strings.
The live endpoint returns 30. The archived page even names its own replacement, two
lines under its own list: "Also see `https://www.reddit.com/api/v1/scopes` for a list
of all available scopes." Treat every token fact below the same way: usable, and one
outdated page away from wrong.

### The app types

> "Web app: Runs as part of a web service on a server you control. Can keep a secret."
>
> "Installed app: Runs on devices you don't control, such as the user's mobile phone.
> Cannot keep a secret, and therefore, does not receive one."
>
> "Script app: Runs on hardware you control, such as your own laptop or server. Can
> keep a secret. Only has access to your account."
>
> <https://github.com/reddit-archive/reddit/wiki/OAuth2>

Script is the shape commentdraft has: one operator, one account, one laptop. The
constraint that comes with it is stated on the quick start page rather than the app
types page:

> "These examples will only work for script type apps, which will ONLY have access to
> accounts registered as 'developers' of the app and require the application to know
> the user's password."
>
> <https://github.com/reddit-archive/reddit/wiki/OAuth2-Quick-Start-Example>

### The two flows

The password grant, for a script app:

```
POST https://www.reddit.com/api/v1/access_token
  Authorization: Basic base64(client_id:client_secret)
  Content-Type: application/x-www-form-urlencoded

  grant_type=password&username=USER&password=PASS
```

The documented response shape, quoted from the same page:
`{"access_token": ..., "expires_in": 3600, "scope": "*", "token_type": "bearer"}`.

This flow hands your account password to the process at every renewal. Whether it
works at all on an account with two factor authentication enabled is not documented by
Reddit in either direction, and no primary statement was found. If your account has
2FA on, assume this path needs testing before it needs designing around.

The authorization code flow, which never sees the password:

1. Send the browser to the authorization URL:

   ```
   https://www.reddit.com/api/v1/authorize
     ?client_id=CLIENT_ID
     &response_type=code
     &state=RANDOM_STRING
     &redirect_uri=URI
     &duration=permanent
     &scope=read+history+submit
   ```

   `state` is not decoration. Reddit's own description: "You should generate a unique,
   possibly random, string for each authorization request... you should verify that it
   matches the one you sent."

2. Exchange the returned `code`:

   ```
   POST https://www.reddit.com/api/v1/access_token
     Authorization: Basic base64(client_id:client_secret)

     grant_type=authorization_code&code=CODE&redirect_uri=URI
   ```

   The `redirect_uri` must match the registered one exactly, and Reddit says so twice.
   A `code` is one time use: `invalid_grant` means "The code has expired or already
   been used".

3. Use the token against the other host:

   > "API requests with a bearer token should be made to `https://oauth.reddit.com`,
   > NOT `www.reddit.com`."
   >
   > <https://github.com/reddit-archive/reddit/wiki/OAuth2>, bolded in the original

   Header: `Authorization: bearer TOKEN`. An unauthenticated `GET
   https://oauth.reddit.com/api/v1/me` returns HTTP 403, observed 2026-08-01.

`duration=permanent` is what adds a refresh token to the response. `duration` is also
where the archived page states the lifetime: "All bearer tokens expire after 1 hour."

### Renewing and revoking

Renewal is `grant_type=refresh_token&refresh_token=TOKEN` against the same
`access_token` URL with the same HTTP Basic client auth. Revocation is
`POST https://www.reddit.com/api/v1/revoke_token` with
`token=TOKEN&token_type_hint=TOKEN_TYPE`. One sentence on that page is the one to read
twice:

> "Revoking a refresh token will also revoke any related access tokens!"

### The scopes

Thirty, from `https://www.reddit.com/api/v1/scopes`, read 2026-08-01:

```
account          announcements    creddits         edit             flair
history          identity         livemanage       modconfig        modcontributors
modflair         modlog           modmail          modnote          modothers
modposts         modself          modtraffic       modwiki          mysubreddits
privatemessages  read             report           save             structuredstyles
submit           subscribe        vote             wikiedit         wikiread
```

Eleven of those are missing from the archived list every third-party guide copies:
`account`, `announcements`, `creddits`, `livemanage`, `modcontributors`, `modmail`,
`modnote`, `modothers`, `modself`, `modtraffic`, `structuredstyles`. None of the
eleven is needed here. They matter because the list that omits them is the list most
readers will find first.

The four that matter for reading and replying, described in Reddit's own words from
that JSON:

| Scope | Reddit's description | Reddit's section name |
|---|---|---|
| `read` | "Access posts and comments through my account." | Read Content |
| `history` | "Access my voting history and comments or submissions I've saved or hidden." | History |
| `submit` | "Submit links and comments from my account." | Submit Content |
| `privatemessages` | "Access my inbox and send private messages to other users." | Private Messages |

Two more you may want and should request deliberately rather than by habit:
`identity` ("Access my reddit username and signup date.") and `edit` ("Edit and delete
my comments and submissions."). A tool that only drafts and sends needs neither.

Put the token in the environment variable your config would name, in a `.env` file
next to `config.toml`, never in `config.toml` itself. Client secret and account
password go in the same place and nowhere else.

## Reading and replying

Every path below is from `https://www.reddit.com/dev/api/oauth`, read 2026-08-01,
with the scope tag Reddit prints against it.

| Call | Scope | Reddit's own description |
|---|---|---|
| `GET [/r/subreddit]/comments/article` | `read` | "Get the comment tree for a given Link `article`." |
| `GET /user/{username}/submitted` | `history` | One of the `/user/{username}/{where}` listings, under the History heading |
| `GET /message/inbox`, `/unread`, `/sent` | `privatemessages` | The three `/message/{where}` listings |
| `GET [/r/subreddit]/api/info` | `read` | "Return a listing of things specified by their fullnames. Only Links, Comments, and Subreddits are allowed." |
| `GET /api/morechildren` | `read` | "Retrieve additional comments omitted from a base comment tree... up to 100 at a time." |
| `POST /api/comment` | see below | "Submit a new comment or reply to a message." |
| `POST /api/editusertext` | `edit` | "Edit the body text of a comment or self-post." |
| `POST /api/del` | `edit` | "Delete a Link or Comment." |
| `GET /api/v1/me` | `identity` | The signed-in account |

### Three places the scope is not where the name says

The first is the reply endpoint. `POST /api/comment` carries the endpoint-level tag
`any`, under a heading that reads "Any Scope: Endpoint is accessible with any
combination of other OAuth 2 scopes." A reader who scans the tag concludes no scope is
needed. The real requirement is inside the prose describing the `parent` parameter:

> "`parent` is the fullname of the thing being replied to. Its value changes the kind
> of object created by this request: the fullname of a Link: a top-level comment in
> that Link's thread. (requires `submit` scope) / the fullname of a Comment: a comment
> reply to that comment. (requires `submit` scope) / the fullname of a Message: a
> message reply to that message. (requires `privatemessages` scope)"
>
> The three cases are a bulleted list on Reddit's page and are run together here with
> slashes

The second is the inbox. A reply to one of your comments arrives there, and the scope
that reads it is `privatemessages`. Reddit's taxonomy files "somebody answered you"
and "somebody sent you a DM" under one heading. A client that asks for `read submit`,
the two scopes whose names match the job, has authorization for everything except the
listing that carries reply notifications, and nothing in the grant says so.

The third is enumerating your own posts. `/comments/article` needs an article id, and
the listing that hands you your own article ids is `/user/{username}/submitted`, which
sits under the History heading and needs `history`.

So the Facebook-shaped loop, read your own posts and then the comments under each,
costs three scopes on Reddit, and not one of them is named after what it does here:

```
read history submit
```

Add `privatemessages` if you also want replies to your own comments, which is where
most of a Reddit thread's conversation actually is.

### Ids come in two spellings, in one loop

Reddit's fullname prefixes, from the reference page: `t1_` Comment, `t2_` Account,
`t3_` Link, `t4_` Message, `t5_` Subreddit, `t6_` Award.

`GET /comments/article` takes `article`, documented as "ID36 of a link", with no
prefix. `POST /api/comment` takes `thing_id`, documented as "fullname of parent
thing", with one. A connector reads a tree keyed one way and writes to it keyed the
other, and `publish_reply(config, parent_id, text)` receives whatever went into the
`id` column of the CSV. That column would have to carry the fullname, because
reconstructing `t1_` from a bare ID36 means guessing the type of the thing you are
about to post under. Facebook's connector already carries a version of this problem
with `98765` against `1122334455_98765`, and it cost a real defect there.

### Every response body is HTML-escaped

> "For legacy reasons, all JSON response bodies currently have `<`, `>`, and `&`
> replaced with `&lt;`, `&gt;`, and `&amp;`, respectively. If you wish to opt out of
> this behaviour, add a `raw_json=1` parameter to your request."
>
> <https://www.reddit.com/dev/api/oauth>

This is the defect most likely to ship unnoticed in a drafting tool. A comment reading
`Tom & Jerry` arrives as `Tom &amp; Jerry`, goes into the CSV that way, reaches the
model that way, appears on the review page that way, and a reviewer reading quickly
approves a reply drafted against text that is not what the customer wrote. Send
`raw_json=1` on every read. There is no cost to it and no ambiguity about it.

### Paging

Listings page by fullname cursor, not by time:

> "To page through a listing, start by fetching the first page without specifying
> values for `after` and `count`. The response will contain an `after` value which you
> can pass in the next request. It is a good idea, but not required, to send an updated
> value for `count` which should be the number of items already fetched."

Listing `limit` is "the maximum number of items desired (default: 25, maximum: 100)".
`/comments/article` is not a listing and documents `limit` as "(optional) an integer"
with no maximum, plus `depth`, `context` ("an integer between 0 and 8"), `truncate`
("an integer between 0 and 50") and `sort` (`confidence`, `top`, `new`,
`controversial`, `old`, `random`, `qa`, `live`).

`commentdraft pull --since` takes "an opaque marker the connector itself defines",
which the CLI help already states. On Reddit that marker would be a fullname cursor or
a client-side timestamp filter, and the choice is the connector's to make and to
document.

### Webhooks

**None exist.** No push, callback, subscription or event model appears in Reddit's API
reference, the Data API Wiki, the Developer Terms or the Data API Terms. A Reddit
connector polls, which is what commentdraft does anyway, and the polling budget is in
[Limits](#limits).

## The 48 hour rule

The earlier research on this platform contained no occurrence of "delete",
"retention" or "48 hours". This section is the correction, and it is the one that
changes what a connector has to be.

Reddit's Data API Wiki, article 16160319875092, edited 2026-05-11:

> "You must remove any user content in your possession that has been deleted from
> Reddit."

> "When posts and comments are deleted, you must delete all content related to the post
> and/or comment (e.g., title, body, embedded URLs, etc.)."

> "When a user account is deleted, you must delete all related user ID info (e.g.,
> t2_*). You must also delete all references to the author-identifying information
> (i.e., the author ID, name, profile URL, avatar image URL, user flair, etc.) from
> posts and comments created by that account."

> "To best comply with this policy, we strongly recommend routinely deleting any stored
> user data and content within 48 hours."

> "Note that retention of content and data that has been deleted, even if
> disassociated, de-identified or anonymized, is a violation of our terms and
> policies."

That last sentence sets its two commas as dashes on Reddit's page; the wording is
otherwise exact. Data API Terms 3.2 states the same obligation as a term rather than a
recommendation:

> "use or retain any User Content, Materials, or data accessed through the Data APIs
> beyond your approved use case, and you must immediately delete any data not required
> for it"
>
> <https://redditinc.com/policies/data-api-terms>, Last Revised July 20, 2026

Note the split. The 48 hours is a recommendation. "Immediately delete any data not
required for it" is not, and neither is "you must remove any user content in your
possession that has been deleted from Reddit". A tool that never checks whether a
comment still exists cannot satisfy the second one at any interval.

### What that means for this design

commentdraft's whole method is to cache comment text and draft against it later. Five
artifacts would hold Reddit data:

| File | What it holds | How the rule reaches it |
|---|---|---|
| `comments.csv` | `id`, `platform`, `author`, `comment`, `post_title` | Body text and an author name, both named in the wiki's own list |
| `out/review.csv` | The same, plus the drafted reply and the decision | Same |
| `out/review.html` | The rendered review page a person reads | Same, and it is the artifact most likely to be left open in a browser tab for a week |
| `pull-state.json` | Every comment id handed over so far | Ids only. See below |
| `out/published.jsonl` | One line per send, with the id Reddit returned | The id of something your own account published |

The first three are 48 hour files under Reddit's recommendation. That collides
directly with the posture `docs/configuration.md` recommends and this project argues
for elsewhere: a read-only deployment that pulls comments and lets a person read the
drafts for a week before any write scope is requested. A week-old `review.html` full
of Reddit comment bodies is exactly the retention the wiki asks you to avoid.

The last two are different and the difference is worth stating precisely. A stored
comment id, and an audit line recording what your own account posted, are not comment
bodies and not author-identifying information. The wiki's explicit examples reach an
account fullname (`t2_`) and an author name; a comment id (`t1_`) is neither. But the
opening sentence is broad, "any user content in your possession", and nobody outside
Reddit can rule on whether an id alone is content. The id-keeping design that makes
`--state` work is both the part most likely to survive this rule and the part that
needs Reddit to say so.

### What a connector would have to add, none of which exists

1. **An expiry.** Nothing in commentdraft deletes anything, ever. `commentdraft
   ingest` refuses to overwrite a file rather than replacing it, which is the opposite
   instinct, and it is the right instinct for a transcription and the wrong one here.
2. **A re-read before drafting, and again before publishing.** A comment pulled on
   Monday and approved on Thursday may have been deleted on Tuesday. Nothing re-checks
   it. Publishing a reply under a deleted comment is the visible half of that failure;
   the invisible half is that the draft was written from text you were required to have
   removed.
3. **Somewhere to record when a row was pulled.** `IN_FIELDS` is `id`, `platform`,
   `author`, `comment`, `post_title`, and the `Platform` protocol's docstring says
   "Exactly that shape, not a superset". A retention clock needs a timestamp per row,
   and there is nowhere to put one without changing the column list that every
   connector, the CSV writer and the CSV reader share.

None of that is optional polish. It is the gap between a tool that can read Reddit and
a tool that keeps the terms it agreed to on the ticket form.

### Where the comment text goes next

Drafting sends the comment body to whatever `[model].base_url` names, which is a third
party of your choosing. Two Reddit clauses point at that:

> "use the Data APIs to encourage or promote illegal activity or violation of third
> party rights (including using User Content to train a machine learning or AI model
> without the express permission of rightsholders in the applicable User Content)"
>
> Data API Terms 3.2

> "You may not use content on Reddit as an input for any model training without
> explicit consent from Reddit."
>
> Article 14945211791892

Inference is not training, and that distinction is doing real work here rather than
being a technicality: the comment is sent so a reply can be written, not so a model can
be fitted. What keeps the distinction true is out of your hands the moment the request
leaves, which is why commentdraft requires `params.provider.data_collection = "deny"`,
nested inside `provider`, on every model entry, checked before the first call of every
run. `docs/platform-policy.md` already says that whether a gateway honours it is
between you and that gateway. On Reddit that stops being a preference and becomes a
term somebody agreed to on your behalf.

## Configuring commentdraft

There is nothing to configure. `[source]` and `[publish]` both take a registered
platform name, `find_platform` is called before any credential is read, and the
registry holds one entry. The output at the top of this page is the whole of it.

What a connector would have to provide, from
`src/commentdraft/platforms/__init__.py`:

- `fetch_comments(config, since) -> list[dict]`, returning rows in `IN_FIELDS` shape
  and nothing wider.
- `publish_reply(config, parent_id, text) -> str`, returning the id Reddit assigned,
  because that id is what answers "what did my account post".
- `SOURCE_KEYS` and `PUBLISH_KEYS` class attributes declaring any config key beyond
  `platform` and `credential_env`. A Reddit connector needs a username for
  `/user/{username}/submitted`, which is one such key, and a key that is not declared
  is invisible to the vocabulary freeze in `tests/test_guarantees.py`.
- More than one credential. Reddit needs a client id, a client secret and either a
  refresh token or an account password. `credential_env` names one variable. Either
  the connector reads a JSON blob out of one variable or the config grows keys, and
  that is a design decision nobody has made.

`docs/configuration.md` is the reference for both tables as they exist today.

## What breaks, and what each failure means

### Calling without OAuth

> "Clients must authenticate with a registered OAuth token. We can and will freely
> throttle or block unidentified Data API users."
>
> "Traffic not using OAuth or login credentials will be blocked, and the default rate
> limit will not apply."
>
> Reddit Data API Wiki

Two separate sentences saying the same thing. There is no anonymous read path to build
against, whatever a public JSON URL appears to give you in a browser.

### A default User-Agent

> "You must use a User-Agent where possible. Change your client's User-Agent string to
> something unique and descriptive, including the target platform, a unique application
> identifier, a version string, and your username as contact information, in the
> following format: `<platform>:<app ID>:<version string> (by /u/<reddit username>)`"
>
> Example: `User-Agent: android:com.example.myredditapp:v1.2.3 (by /u/kemitche)`
>
> "Many default User-Agents (like 'Python/urllib' or 'Java') are drastically limited to
> encourage unique and descriptive user-agent strings."
>
> "NEVER lie about your User-Agent."
>
> Reddit Data API Wiki

The penalty is throttling rather than an error, so a client left on a library default
looks slow rather than misconfigured. And it is a term, not a nicety:

> "You must use the Access Info we provided you (e.g., the OAuth token) when accessing
> the Data APIs, and you will not misrepresent or mask either the user agent or OAuth
> identity when using the Data APIs."
>
> Data API Terms 2.8

### Token endpoint errors

From the archived OAuth2 page, so read them with that section's caveat:

| Symptom | Cause Reddit gives | What you do |
|---|---|---|
| 401 response | "Client credentials sent as HTTP Basic Authorization were invalid" | Check the Basic auth header and the client id and secret |
| `unsupported_grant_type` | "`grant_type` parameter was invalid or Http Content type was not set correctly" | Set `Content-Type: application/x-www-form-urlencoded` |
| `NO_TEXT` for field `code` | "You didn't include the `code` parameter" | Include it in the POST body |
| `invalid_grant` | "The `code` has expired or already been used" | Codes are one time use. Start the authorization again |
| 403 in the browser at `/api/v1/authorize` | "`client_id` is missing or invalid", or "`redirect_uri` is invalid" | Match the registered redirect URI exactly |

### Enforcement, which is the fourth way a token dies

The three usually listed are the one hour expiry, an explicit `revoke_token` call, and
the user removing the app's grant. There is a fourth:

> "We do not tolerate the misuse of Reddit data, and actively work to enforce this
> policy to prevent abuse. Enforcement actions we can take include, but are not limited
> to: Revoking your access tokens. Suspending your app or account. Suspending associated
> accounts, bots, domains, or subreddits."
>
> Responsible Builder Policy, Enforcement. Reddit's three actions are bulleted

A revoked token is indistinguishable at the wire from an expired one until the refresh
also fails. A client that refreshes on 401 without limit will loop against an
enforcement action rather than reporting it.

### Prohibited activity, in Reddit's words

The section those rules sit in opens by saying who it covers, and it covers this
directly. Reddit sets the two inner dashes as typographic characters; they are commas
here and nothing else is changed:

> "This section applies to all users and developers who use or develop apps, including
> bots, AI agents, or non-human operated accounts, with Reddit data. All apps must also
> abide by the Moderator Code of Conduct."
>
> Responsible Builder Policy, Apps and Automated Activity

Read that second sentence twice. The Moderator Code of Conduct binds an app whether or
not its operator moderates anything, which is why the subreddit-rules section below is
not optional reading.

> "Apps must not manipulate Reddit's features (e.g., voting, karma) or circumvent
> safety mechanisms (e.g., user blocking, account bans). Apps must not engage in
> spamming activity through automated posts, comments, or direct messages. This
> includes posting identical or substantially similar content across subreddits."
>
> Responsible Builder Policy, Prohibited App Activities

The last sentence is the one that bites this design, and not for the reason it looks
like. A model grounded in one source document produces near-identical replies to
near-identical questions. Twenty answers that are twenty rewordings of one paragraph,
posted across four subreddits, is "substantially similar content across subreddits" by
Reddit's own words at any volume. `docs/limits.md` explains why nothing in this design
can prevent that while a draft is being written, and what `find_repetition` and the run
report tell you afterwards. On Reddit that report is not a quality signal. It is the
thing to read before approving.

Reddit's User Agreement adds the site-wide floor:

> "Use the Services in any manner (automated, including via bots, or otherwise) that
> could interfere with, disable, disrupt, overburden, or otherwise impair the Services;"
>
> <https://redditinc.com/policies/user-agreement>, Section 7 "Things You Cannot Do",
> Effective July 1, 2026, Last Revised May 26, 2026

Data API Terms 3.2 adds "use the Data APIs to spam, incentivize, or harass users."

### Subreddit rules, which are not Reddit's rules

Individual subreddits set and enforce their own policy on automated participation,
regardless of what your approved use case says. The Moderator Code of Conduct,
Effective June 5, 2025, makes moderators responsible for it under Rule 1:

> "The content in your subreddit that is subject to the Reddit Rules includes, but is
> not limited to: Posts / Comments / Flairs / Rules / Wiki Pages / Styling / Modmails /
> Bots, automations, and/or apps / Other mod tools"
>
> <https://redditinc.com/policies/moderator-code-of-conduct>, Rule 1. Reddit's list is
> bulleted; the slashes here are the line breaks

Reddit publishes no universal community norm here, so the only reliable move is to read
the rules of each subreddit you would reply in, before you reply there.

### A comment that is filtered or removed

Unknown whether it is visible to you through the API when you are the post's author and
not a moderator. See [What is still unknown](#what-is-still-unknown). A tool that
silently never sees some comments and never says so is worse than one that cannot see
them at all, so this is worth establishing empirically before anyone trusts a pull to
be complete.

## Limits

`docs/limits.md` covers what commentdraft cannot do regardless of platform. This
section is what Reddit imposes.

### Rate limits

> "We enforce rate limits for those eligible for free access usage of our Data API. The
> limit is: 100 queries per minute (QPM) per OAuth client id"
>
> "QPM limits will be an average over a time window (currently 10 minutes) to support
> bursting requests."
>
> Reddit Data API Wiki, edited 2026-05-11

Per client id, not per account and not per endpoint. Two things follow. A burst of 150
in one minute can pass if the surrounding ten minutes are quiet, and a steady 90 per
minute can be throttled if an earlier burst has not rolled off. Build against the
headers rather than a counter of your own:

> `X-Ratelimit-Used`: "Approximate number of requests used in this period"
>
> `X-Ratelimit-Remaining`: "Approximate number of requests left to use"
>
> `X-Ratelimit-Reset`: "Approximate number of seconds to end of period"
>
> Same page

Measured, not quoted: three consecutive unauthenticated `GET` requests to
`https://www.reddit.com/api/v1/scopes` on 2026-08-01 returned `x-ratelimit-used` 5, 6,
7; `x-ratelimit-remaining` 95.0, 94.0, 93.0; `x-ratelimit-reset` 369, 368, 368. So the
headers are present and the counter increments per request, on a budget of 100 over a
window ending in the same second across all three. That is the unauthenticated budget,
which is not the documented 100 QPM per OAuth client id, and Reddit says unauthenticated
traffic will be blocked in any case. **Nobody has read these headers on an authenticated
call**, so whether the same three appear there, with the same names, is unverified.
`https://oauth.reddit.com/api/v1/me` without a token returns 403 and no rate limit
headers at all.

### Replies per day

**Unpublished.** Reddit names no per-day ceiling on comments or replies in the Data API
Wiki, the Data API Terms or the Developer Terms. Reddit is known informally for
karma-based and account-age-based throttling on posting, the "you are doing that too
much" refusal, and no primary source states its numbers. Any figure you find is
folklore. Do not promise an operator a daily volume.

### Chat limits are not comment limits

The Data API Wiki does publish daily ceilings, and they are for Reddit's chat feature.
Reddit's three lines, under "Free access usage also includes the following rate limits
for chat messages":

> "2,000 messages per day per recipient"
>
> "3,000 messages per day total"
>
> "Bot API users can join up to 300 chat rooms per day."

None of the three applies to comment replies. They are quoted here so nobody borrows
them.

### Quota costs per endpoint

**Unpublished.** Reddit expresses cost as requests against one shared budget, and
publishes no per-endpoint weighting.

### Cost

The free tier is real and currently documented at the 100 QPM above. Beyond it:

> "Reddit offers both free and paid access. Whether your use will require paid access
> depends on how you access and use the data... Bulk exporting of Reddit data will be
> significantly limited by default, however, and select developers who require broader
> access to Reddit data may be charged fees to lift those limits."
>
> Article 14945211791892

> "Reddit reserves the right to charge fees for future use or access to the Data APIs,
> rates to be determined at Reddit's sole discretion."
>
> Data API Terms 3.1

**No rate card exists on any live Reddit page.** The widely-repeated figure of $0.24
per 1,000 API calls comes from press coverage of an April 2023 announcement and appears
on none of the Reddit-owned pages read for this document. Do not budget from it, and do
not quote it to anyone. Ask for a current figure on the ticket if your use crosses into
the commercial lane.

## What is still unknown

Every item here failed to resolve against a primary source, or cannot resolve without
an account. None of it is smoothed over above.

**How long approval takes.** Reddit publishes no SLA, no queue position and no expected
range for the Data API access request. This is the single largest planning risk on the
page, and it is unanswerable from outside.

**Whether an author replying about a book they sell is commercial use.** Reddit's nine
published examples are all about monetizing Reddit content, data or access, and none
describes this. The clause they illustrate is broader than they are and Reddit holds
sole discretion. See [Commercial use](#commercial-use). This is unresolved in Reddit's
own text, not merely unresearched.

**What a commercial agreement costs.** Reddit says a contract is required and publishes
no rate.

**Everything about tokens.** The one hour lifetime, `duration=permanent`, the refresh
grant, `revoke_token`, `oauth.reddit.com` and the three app types are all single-sourced
to a repository Reddit archived in 2017, under Reddit's own warning that such pages may
be out of date. That warning already proved out once, on the scope list. Minting one
token settles all six at once.

**Whether the password grant works with two factor authentication enabled.** No Reddit
statement in either direction was found. Reddit's own support material recommends
enabling 2FA, which makes this the likely first wall for anyone following the quick
start.

**Which field distinguishes a comment reply from a private message in the inbox.**
Third-party tooling refers to a `was_comment` boolean. That field name appears on no
Reddit-owned page read for this document. A connector polling `/message/unread` needs
this and cannot get it without a live response.

**Whether comments removed by a subreddit's filter are visible to the post's author.**
Nothing in the API reference, the Data API Wiki or either terms document describes
visibility of filtered or removed content by viewer role. Post a test comment, have a
filtered account reply, and read `/comments/article`. That settles it in an afternoon
and nobody has spent the afternoon.

**Whether a stored comment id counts as user content under the deletion rule.** Reddit's
examples name account fullnames and author-identifying fields; a comment id is neither,
and the governing sentence is broader than the examples. `pull-state.json` exists
entirely to hold those ids. See [The 48 hour rule](#the-48-hour-rule).

**Whether authenticated responses carry the three rate limit headers.** Measured on
unauthenticated calls only.

**Whether an app that does not exist yet can use the App Registration page**, and what
happens to the profile label requirement after the August 30, 2026 date on it. The page
requires a login before it says more.

**Whether any disclosure of software-assisted reply text is required.** The Responsible
Builder Policy requires app registration, a developer profile and an App profile label,
and prohibits circumventing Reddit's own labeling. It does not require a sentence inside
the reply, and no such clause was found in the Developer Terms, the Data API Terms or
the User Agreement. Absence of a found clause is not proof of absence. commentdraft
renders `bot_disclosure_text` into every prefix regardless, with no setting that turns
it off, and `docs/platform-policy.md` maps that to the rules it was built for. Operators
in regulated sectors should take their own advice rather than this page's.

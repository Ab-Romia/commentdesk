# Platform guides

Eight pages, one per platform, each written from the platform's own primary sources and
each saying out loud how far the checking went. One of the eight documents a connector
that exists. The other seven document what it would take to build one, so that whoever
does, or decides not to, starts from the source instead of from a blog post.

- [Facebook Pages](facebook.md), the connector that ships
- [Instagram](instagram.md)
- [Threads](threads.md)
- [YouTube](youtube.md)
- [Reddit](reddit.md)
- [X](x.md)
- [TikTok](tiktok.md)
- [LinkedIn Pages and profiles](linkedin.md)

Every page was read against live documentation on **2026-08-01**. Prices, review
timelines and policy quotes decay, so each page carries the date it was read and the
revision stamp of the document it quotes. Re-read before you plan around any of it.

## The published blocker is rarely the real one

This is the thing that came out of writing all eight and would not have come out of
writing any one of them. On every platform where the received wisdom names an obstacle,
the obstacle it names is either out of date or is standing in front of a different one.

X is the clearest case. The received wisdom is that money is the barrier, and the
$100, $200 and $5,000 figures still dominate search results. Those are prices for a
product X stopped selling on 2026-02-06, and at this tool's shape of workload the
metered bill is about three dollars a month. What replaced the money is a requirement for
prior written approval from X before AI-generated replies are deployed, sourced twice,
with no published turnaround, no queue position and no appeal. A cost you can pay became
a permission with no clock on it, which is worse for planning and reads better in a
headline.

TikTok is repeated everywhere as having no comment API. It has two documented comment
endpoints, on `business-api.tiktok.com`, which is a different product line from the
`developers.tiktok.com` portal every tutorial means. What TikTok actually refuses is not
the feature but the applicant: it will not onboard individual developers at all, and says
so on its registration page. The refusal is aimed at who is asking rather than at what is
being asked for.

Threads publishes App Review as the gate. App Review is not reachable until the app is
connected to a Business that has completed Business Verification, which is company
paperwork rather than a demonstration of software and which only a Business admin can
complete. An operator who reads "App Review", budgets a week and starts recording a
screencast is one document set short of being able to submit.

LinkedIn publishes a two-stage partner review as the gate, and the review is the smaller
problem. The Marketing API Terms prohibit exporting Member Data to any third party, and
define Member Data to include a member's comment. This tool sends every comment's text to
whatever `[model].base_url` names. Whether that gateway is a third party or the operator's
own service provider is unsettled, and it sits upstream of the design rather than in front
of it. Passing the review would not answer it.

The pattern is worth stating once because it changes how you read the rest of these pages.
The section to read on each one is not the one about the published gate. It is
"What is still unknown", where the thing that actually stops you tends to be sitting.

## What each platform costs

| Platform | Connector | Read | Reply | What stands in the way | Roughly what it costs to get through |
|---|---|---|---|---|---|
| [Facebook Pages](facebook.md) | **Yes, the only one** | Documented | Documented, and Meta documents two readings of the endpoint | Nothing to clear. An operator who owns the Page and makes their own app needs no App Review and no Business Verification | No fee. Our estimate is under an hour from a standing start |
| [Instagram](instagram.md) | No | Documented | Documented | Nothing, for your own professional account at Standard Access. The comments webhook is the exception and needs Advanced Access | No fee. Polling instead of webhooks is the price of skipping App Review |
| [Threads](threads.md) | No | Documented | Documented, two-step container then publish | Nothing, for the single-operator path. Anything beyond it needs App Review, which sits behind Business Verification | No fee. Business Verification is company paperwork, not a build |
| [YouTube](youtube.md) | No | Documented | Documented, 50 units a call | A 10,000 unit daily quota, so 200 replies a day at the ceiling. An app left in Testing gets refresh tokens that expire in 7 days | No fee, and no pricing page exists. OAuth verification, "can take up to 10 days", once anyone but you uses it |
| [Reddit](reddit.md) | No | Documented | Documented | Access is granted rather than taken. The Responsible Builder Policy requires approval before the first call, through a support ticket | Free at 100 queries per minute per OAuth client id. No turnaround is published for the ticket |
| [X](x.md) | No | Documented, 7 day search window | Unsettled. A programmatic reply is permitted when the author summoned you, and nobody has established whether replying on your own post counts | Prior written approval from X before AI-generated replies are deployed. No published turnaround and no self-serve path | About $3 a month at 500 comments read and 250 replies published. Enterprise is the fallback and publishes no price |
| [TikTok](tiktok.md) | No | Documented | Documented | The developer of record must be a company with a matching domain. A solo consultant cannot register | No published fee. Three reviews: "three business days", "2 to 3 business days", and a form with no published turnaround |
| [LinkedIn](linkedin.md) | No | Documented | Documented | A two stage partner review, and above it the Member Data question, which no page read could answer | No price published on any LinkedIn property. No SLA published for either review stage |

"Documented" throughout means the platform publishes the call. On seven of the eight rows
nobody has made it. Each page's own verification section says which of its claims were
read twice, which rest on one reading, and which cannot be settled without credentials.

## The order worth attempting them in

1. **[Facebook Pages](facebook.md).** It is built, and it is the only route on this list
   where nothing is queued and nobody reads anything. Start here even if Facebook is not
   the platform you want, because it is the one that tells you whether the rest of the
   tool suits you before you spend a review cycle finding out.

2. **[Instagram](instagram.md).** Same Meta app, same Graph host, same token concepts, and
   for your own professional account the same absence of review. The work is a connector
   rather than an application. Accept polling in the first version and the whole App
   Review branch disappears.

3. **[Threads](threads.md).** Also gate-free for a single operator, but on its own hosts
   with its own two-step publish and its own two expiry clocks. More build than Instagram
   for the same amount of paperwork, which is none.

4. **[YouTube](youtube.md).** No review and no money for your own channel, and the
   approval gate this tool already has is a policy requirement here rather than a product
   opinion, which makes it the platform whose rules fit the design best. What it costs is
   arithmetic: 50 units a reply against 10,000 units a day, minus whatever polling spends.

5. **[Reddit](reddit.md).** Permissive rules and a free tier, behind a request with no
   published turnaround. File the ticket early, because it is the only thing on this list
   where the waiting can start before the building does. Read the 48 hour deletion rule
   first: it reshapes what a review queue is allowed to keep.

6. **[X](x.md).** Cheap and self-serve to get keys, and then two questions with no
   published answer: whether the approval requirement covers a tool with a person
   approving each reply, and whether replying on your own post counts as being summoned.
   The second is settleable in an afternoon with a live call and it can make the first
   moot, so settle it before writing any connector code.

7. **[TikTok](tiktok.md).** Attempt only if the developer of record is a company. The
   requirement lands on whoever registers the app and not on the account being moderated,
   so a creator with a personal account can be covered by an app a company they work with
   registers. If that separation is not available to you, the answer is no and the rest of
   the page is reference.

8. **[LinkedIn](linkedin.md).** Last, because the review is long and the question above it
   is unanswered. Settle the Member Data reading with somebody qualified before spending a
   fortnight on a partner application, since a no there ends the project rather than
   delaying it.

The first four need no permission from anybody. The last four each need a human at the
platform to say yes, and three of the four publish no idea of how long that takes.

## Two things that corrupt the comment text before you ever see it

Neither of these is in either research file. Both mean the text arriving in `comments.csv`
is not the text the person typed, and both would corrupt the drafting and the review page
without anything looking wrong.

**YouTube withholds the original text from the channel owner.**
`snippet.textOriginal` is documented as "The original, raw text of the comment as it was
initially posted or last updated. The original text is only returned to the authenticated
user if they are the comment's author." A channel owner reading a viewer's comment is not
that comment's author, so the field is withheld and `snippet.textDisplay` is what a
connector gets. Google on what that is:

> "The comment's text. The text can be retrieved in either plain text or HTML. (The
> comments.list and commentThreads.list methods both support a textFormat parameter,
> which specifies the chosen text format.) Even the plain text may differ from the
> original comment text. For example, it may replace video links with video titles."
>
> <https://developers.google.com/youtube/v3/docs/comments> (Last updated 2026-06-01 UTC)

Two things follow. The default `textFormat` is `html`, so a connector that does not set
`plainText` puts HTML entities into the model's prompt and onto the review page. And even
with `plainText` set, the text is Google's rendering rather than the commenter's words, so
a reply that quotes the comment back can quote something that was never written. See
[The row shape, and where it does not fit](youtube.md#the-row-shape-and-where-it-does-not-fit)
on the YouTube page.

**Reddit escapes ampersands in every JSON body unless you ask it not to.**

> "For legacy reasons, all JSON response bodies currently have `<`, `>`, and `&`
> replaced with `&lt;`, `&gt;`, and `&amp;`, respectively. If you wish to opt out of
> this behaviour, add a `raw_json=1` parameter to your request."
>
> <https://www.reddit.com/dev/api/oauth>

A comment reading `Tom & Jerry` arrives as `Tom &amp; Jerry`. It goes into the CSV that
way, reaches the model that way, and `commentdraft review` escapes it again when it
renders the HTML, so the reviewer reads `Tom &amp; Jerry` on the page and approves a reply
drafted against text nobody wrote. Send `raw_json=1` on every read. There is no cost to it
and no ambiguity about it. See
[Every response body is HTML-escaped](reddit.md#every-response-body-is-html-escaped).

The general lesson for anyone building a connector against any of these: read the field
documentation for the comment body itself, and not stop at the endpoint that returns it.
Two of eight platforms hand back something other than what was typed, and neither says so
at the endpoint.

## The Reddit deadline, and what it turned out to be

The Reddit guide records an August 30, 2026 date on Reddit's App Registration page, which
is 29 days from the date on this page. It was checked on 2026-08-01 and it is real, and it
is not an obligation. Reddit's words:

> "Apps that register by August 30, 2026, may be eligible to claim a $1,000 porting
> bounty as part of Reddit's $1,000,000 Developer Platform App Migration Program."
>
> <https://developers.reddit.com/app-registration>

Three things about it decide whether it affects you.

It is an offer rather than a deadline. Registration itself is a standing requirement under
the Responsible Builder Policy's App Transparency clause, with no date attached and no
sign of expiring. What expires on August 30 is eligibility for the bounty.

It is aimed at apps that already exist. The page describes itself as "Register your
existing apps" and opens "If you have apps that use Reddit's Data API, register them so
people can better recognize your apps and differentiate them from human accounts on the
platform." Nobody building from these pages has an existing Data API app, because access
has to be granted first and the ticket has no published turnaround.

It requires a login before it says anything more, and it requires a person: "You'll need a
human Reddit account to register."

So it changes nothing for a reader here, and it is on this page because a date in that
shape is exactly the kind of thing a reader would otherwise rearrange a month around.
If you are already running a Reddit Data API app, it is worth an afternoon. If you are
reading these pages to decide whether to build one, it is not your deadline.

## What is not on these pages

Two documents carry the parts that are the same everywhere, and the platform guides link
into them rather than restating them.

[`docs/platform-policy.md`](../platform-policy.md) maps each safety property in this tool
to the clause that made it necessary, including the YouTube clause that turns the approval
gate from a product opinion into a policy requirement, and the EU AI Act articles behind
the disclosure setting. It is where to look when a reviewer asks why a control exists.

[`docs/limits.md`](../limits.md) is what the tool cannot do regardless of platform:
repetition that can be reported and not prevented, a pull state file that remembers ids
and never shrinks, a run that overwrites its own output, and the list of English strings
the engine owns. Several platform pages point at it where a platform rule and a tool limit
meet, and the meeting point is usually where a connector author has a decision to make.

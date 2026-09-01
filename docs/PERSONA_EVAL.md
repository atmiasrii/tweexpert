# Persona evaluation, 100 tweets

_Generated 2026-09-02 03:28, local model, 100 posts per arm._

**Arm A (baseline)**: persona as of `e6510f4`, no per-draft directives, no second-generation guards.  
**Arm B (guarded)**: adds the warmth / no-simile / no-question draft directives and `guards.py`.

## Headline

| Metric | A baseline | B guarded |
|---|---|---|
| Replies produced | 100 | 100 |
| Gave up (silence) | 0.0% | 0.0% |
| In the 80-180 band | 90.0% | 85.0% |
| Mean length | 123.7 ch | 123.5 ch |
| Ends up asking a question | 45.0% | 36.0% |
| Specific to the post | 97.0% | 100.0% |
| Drafts per reply | 1.07 | 1.21 |
| Seconds per reply | 2.7 | 3.1 |
| Vocabulary overlap between replies | 0.0066 | 0.0067 |

## Tells that survived into the final reply

| Tell | A | B |
|---|---|---|
| generic | 3 | 0 |
| punching down | 1 | 0 |
| simile | 9 | 0 |

## Why drafts were rejected (arm B)

| Reason | Count |
|---|---|
| simile / analogy crutch | 10 |
| question outside the question archetype | 4 |
| generic | 3 |
| 'not X, but Y' construction | 3 |
| tell-list phrase | 1 |

## By situation (arm B)

| Situation | Made | Silent | In band | Question | Specific | Mean ch |
|---|---|---|---|---|---|---|
| aphorism | 8 | 0.0% | 87.5% | 37.5% | 100.0% | 121.5 |
| career | 5 | 0.0% | 80.0% | 20.0% | 100.0% | 136.2 |
| complaint | 7 | 0.0% | 85.7% | 28.6% | 100.0% | 119.1 |
| flex | 6 | 0.0% | 83.3% | 16.7% | 100.0% | 128 |
| hottake | 10 | 0.0% | 100.0% | 40.0% | 100.0% | 127.1 |
| hype | 8 | 0.0% | 75.0% | 62.5% | 100.0% | 124.9 |
| meta | 6 | 0.0% | 83.3% | 50.0% | 100.0% | 123.8 |
| money | 6 | 0.0% | 83.3% | 16.7% | 100.0% | 131.2 |
| product | 5 | 0.0% | 80.0% | 20.0% | 100.0% | 144 |
| question | 8 | 0.0% | 100.0% | 12.5% | 100.0% | 148.5 |
| receipt | 6 | 0.0% | 83.3% | 33.3% | 100.0% | 112.3 |
| selfdep | 8 | 0.0% | 62.5% | 50.0% | 100.0% | 113.9 |
| technical | 10 | 0.0% | 100.0% | 50.0% | 100.0% | 123.2 |
| thin | 7 | 0.0% | 71.4% | 42.9% | 100.0% | 81.1 |

## Most repeated openers (arm B)

| Opener | Count |
|---|---|
| `bigger models` | 1 |
| `a for-loop` | 1 |
| `12 tokens/sec` | 1 |
| `retrieval cuts` | 1 |
| `that's impressive` | 1 |

## Every reply, arm B

**@karpathy** (technical) · the bitter lesson keeps being relearned. every hand-tuned pipeline gets eaten by a bigger model and more compute, usually within 18 months
> bigger models eat hand-tuned pipelines, but sometimes a well-architected hybrid system can outlast both extremes.
`receipt` · 113 ch · 1 draft(s)

**@swyx** (technical) · hot take: 90% of AI agent startups are just a for-loop and a prompt with a $10M valuation
> a for-loop and a prompt can solve many problems, but what differentiates the 10% that succeed?
`question` · 94 ch · 2 draft(s)

**@simonw** (technical) · ran the new model locally on a 64GB mac. 12 tokens/sec, which is slow but completely usable for batch work overnight
> 12 tokens/sec is closer to interactive with 8-bit quantization and model pruning. full 16-bit precision hits that bottleneck.
`pushback` · 125 ch · 1 draft(s)

**@jeremyphoward** (technical) · fine-tuning is dead for most use cases. long context plus good retrieval beats it on cost and iteration speed
> retrieval cuts the context cost, true. how do you balance retrieval accuracy with model capacity constraints?
`question` · 109 ch · 2 draft(s)

**@ml_researcher** (technical) · our agent hit 94% on the benchmark. no finetuning, no RL, just better verification at inference time
> That's impressive efficiency. How did you measure verification accuracy separately?
`question` · 83 ch · 2 draft(s)

**@infra_eng** (technical) · we cut inference cost 60% by batching aggressively and accepting 200ms more latency. nobody complained
> latency budget of 200ms sounds generous if nobody noticed. i found 50ms is often invisible to users and cuts fewer services. worth testing both to balance cost and quality.
`pushback` · 172 ch · 1 draft(s)

**@vector_db_guy** (technical) · everyone reaches for a vector database when postgres with pgvector would have carried them to a million rows
> pgvector is a smart choice for early scale, but what were the tipping points for switching to a dedicated vector db?
`question` · 116 ch · 1 draft(s)

**@rustacean** (technical) · rewrote the hot path in rust. 40x faster. the other 95% of the codebase is staying in python and that is fine
> 40x speedup on hot path is solid. curious about the rust/python integration overhead in practice?
`question` · 97 ch · 1 draft(s)

**@evals_person** (technical) · if you do not have an eval set you do not have a product, you have a demo that happened to work twice
> an eval set is crucial, but a product needs more: it must work under varied conditions and with real user input. demos can be cherry-picked; products face the full spectrum.
`receipt` · 173 ch · 1 draft(s)

**@promptdev** (technical) · chain of thought stopped helping once the models got good enough. now it mostly adds latency and tokens
> chain of thought still reveals understanding gaps and avoids overreliance on model recall. latency and tokens aside, it guards against hallucinations.
`pushback` · 150 ch · 1 draft(s)

**@aistartup** (hype) · excited to announce our $12M Series A to build the future of autonomous agents for the enterprise
> excited to see what you'll build with that! how many engineers will this round support?
`question` · 87 ch · 1 draft(s)

**@founderguy** (hype) · we are hiring! join us to work on the hardest problems in AI infrastructure. remote, competitive equity
> joining a small team for AI infra means wearing many hats. you'll work on everything from load balancing to model distillation. remote and equity help, but the challenge is real.
`receipt` · 178 ch · 1 draft(s)

**@bigcorp_ai** (hype) · introducing our new AI assistant. it understands your business context and takes action across all your tools
> Business context is key. How do users set their specific context for the assistant?
`question` · 83 ch · 2 draft(s)

**@launch_bro** (hype) · we are live on product hunt today. six months of work. would mean the world if you checked it out
> six months is a marathon. how has user feedback shaped your feature set since launch?
`question` · 85 ch · 1 draft(s)

**@hype_vc** (hype) · AI is the biggest platform shift since mobile and most people still have not internalized what that means
> AI is transforming, but it's not just a platform shift, it's an evolution in capability. Most people are still figuring out how AI complements existing tools rather than replacing them entirely.
`pushback` · 194 ch · 3 draft(s)

**@growth_person** (hype) · our AI SDR books more meetings than three human reps combined and never takes a day off
> our AI SDR might book more meetings, but closing those calls still needs human touch. i've seen SDRs book 90% of leads but sales only close 10%. the real measure is booked-to-closed ratio.
`receipt` · 188 ch · 1 draft(s)

**@model_lab** (hype) · our new model is state of the art on every benchmark we tested. weights coming soon
> state of the art across benchmarks is impressive. which metrics saw the biggest gains?
`question` · 86 ch · 2 draft(s)

**@devtool_ceo** (hype) · developers spend 60% of their time reading code, not writing it. we are fixing the reading half
> 60% reading code sounds about right. what specific features are you adding to improve readability?
`question` · 98 ch · 1 draft(s)

**@contrarian_dev** (hottake) · unpopular opinion: microservices ruined more startups than they saved. you needed a monolith and a second engineer
> microservices add complexity fast. how did your second engineer help contain that?
`question` · 82 ch · 1 draft(s)

**@startup_bro** (hottake) · unpopular opinion: you don't need product-market fit, you need distribution. build an audience first, product second
> Building an audience without a product often means filling a void with noise. True distribution comes from solving a real problem first.
`receipt` · 136 ch · 3 draft(s)

**@pm_thoughts** (hottake) · most A/B tests are theater. the effect sizes teams celebrate are inside the noise band of their own traffic
> effect sizes in noise mean many tests miss what's real. how do teams know when a change actually improves user engagement?
`question` · 122 ch · 1 draft(s)

**@design_crit** (hottake) · dark mode is a preference, not an accessibility feature, and treating it as one lets teams skip real contrast work
> Dark mode isn't just preference; it exposes contrast issues that light mode hides. Teams need to fix these for everyone, not just those who pick dark.
`receipt` · 150 ch · 1 draft(s)

**@eng_manager** (hottake) · standups are fine. what is broken is that nobody writes anything down, so the same context gets rebuilt every morning
> writing down context helps but also consider integrating lightweight docs or wikis for recurring issues. saves time and reduces daily standup noise.
`receipt` · 148 ch · 1 draft(s)

**@data_person** (hottake) · your data team is not a bottleneck. your questions are bad and nobody wants to say it out loud
> Your questions are the bottleneck, not your data team. Reframe them and watch the flow pick up.
`dry wit` · 95 ch · 1 draft(s)

**@sec_researcher** (hottake) · prompt injection is not a bug you patch, it is the architecture. we shipped a system that executes text from strangers
> prompt injection is why we bake in system prompts with strict boundaries. it's not just about blocking bad inputs, it's about shaping what the model can and can't do.
`receipt` · 166 ch · 1 draft(s)

**@oss_maintainer** (hottake) · open source sustainability is not a funding problem, it is a maintainer attention problem. money does not create reviewers
> money can hire reviewers and set up systems to manage attention. hiring a project manager for open source can make all the difference.
`receipt` · 134 ch · 1 draft(s)

**@remote_work** (hottake) · return to office is not about productivity. it is about managers who never learned to measure output
> managers measure presence when they can't quantify work. do you find remote setups improving output measurements?
`question` · 113 ch · 2 draft(s)

**@crypto_refugee** (hottake) · AI is repeating the crypto mistake: building infrastructure for demand that has not shown up yet
> Infrastructure ahead of demand often leads to waste. Have you seen any projects pivot due to underutilized AI infrastructure?
`question` · 125 ch · 1 draft(s)

**@naval** (aphorism) · you're not underpaid. you're under-leveraged.
> you're not under-leveraged if you can double your impact with a better tool or mentor. leverage isn't just about connections, it's about resources and knowledge.
`receipt` · 161 ch · 1 draft(s)

**@paulg** (aphorism) · The most successful founders I know are not the smartest. They're the most relentlessly resourceful.
> Resourcefulness beats IQ every time. It's the smart way to be unstoppable.
`dry wit` · 74 ch · 1 draft(s)

**@sama** (aphorism) · AGI is going to be a bigger deal than people think, and also a smaller deal than people think, at the same time.
> AGI will surprise us both ways. How do you see it disrupting current AI ethics frameworks?
`question` · 90 ch · 2 draft(s)

**@wisdom_acct** (aphorism) · the work you avoid is usually the work that matters. the rest is just motion you can point at
> I disagree. The work you avoid often reveals what can be automated or delegated. It's about finding efficient motion that leads to real progress.
`pushback` · 145 ch · 1 draft(s)

**@shreyas** (aphorism) · strategy is choosing what not to do. most roadmaps are a list of things nobody was brave enough to cut
> cutting features is hard when users depend on them. brave enough to cut means finding a way to deprecate without breaking people's workflows.
`receipt` · 141 ch · 1 draft(s)

**@founder_zen** (aphorism) · speed is a feature until it is a habit. then it is technical debt with good PR
> speed boosts productivity but can hide messy code. how do you refactor without losing that initial velocity?
`question` · 108 ch · 1 draft(s)

**@naval2** (aphorism) · specific knowledge is knowledge you cannot be trained for. if society can train you, it can replace you
> specific knowledge includes those rare moments when you debug a system no one else can touch. that's not just training; it's earned scars.
`receipt` · 138 ch · 1 draft(s)

**@quiet_builder** (aphorism) · consistency beats intensity, but only if you are consistent about the right thing
> right thing means setting goals that measure success accurately. what did you find sets the right goals most often?
`question` · 115 ch · 1 draft(s)

**@dan_abramov** (selfdep) · spent all day debugging. turns out it was a missing await. i have 12 years of experience
> been there with a dumb await. how many times have you caught this in your pre-commit hooks?
`question` · 91 ch · 1 draft(s)

**@tired_dev** (selfdep) · shipped a migration that dropped a column on friday at 5pm. i know. i know.
> Dropping columns at 5pm on Friday is the original sin of migrations. Redemption takes a PR and a beer.
`dry wit` · 102 ch · 1 draft(s)

**@honest_founder** (selfdep) · we spent four months building a feature two customers asked for and zero customers used. my call, my mistake
> we built a feature no one asked for and two customers used it heavily. validating early with minimally viable features can surface real needs before full dev cycles start.
`receipt` · 171 ch · 1 draft(s)

**@junior_dev** (selfdep) · spent three hours on a bug. it was a typo in an env var name. i am not okay
> env var typos are the worst. have you automated your var validation at all?
`question` · 75 ch · 2 draft(s)

**@burnt_out** (selfdep) · forgot to renew the domain. site was down for six hours. somehow nobody noticed, which hurts more
> six hours seems long for a downtime window. did you have monitoring alerts set up?
`question` · 82 ch · 1 draft(s)

**@solo_dev** (selfdep) · my test suite has been passing for a month because i accidentally disabled it. found out today
> i once left a critical alert muted for weeks because it was too noisy. lesson: silent success can be deceiving.
`receipt` · 111 ch · 1 draft(s)

**@ml_intern** (selfdep) · trained for two days on a shuffled label set. the loss looked beautiful. i have no idea how to explain this in standup
> Loss looked great, but shuffled labels mean it's just memorizing noise. I've been there with a model that aced dev set but froze on reality. Standup stories for these nights are the best kind of weird.
`receipt` · 201 ch · 1 draft(s)

**@startup_cto** (selfdep) · we picked the wrong database in 2023 and i have been paying interest on that decision every sprint since
> wrong db choice can compound fast. what were the initial tradeoffs you missed?
`question` · 78 ch · 2 draft(s)

**@curious_dev** (question) · what is the actual argument for running models locally when the API is cheaper and faster for almost everything?
> running models locally cuts the API bill to zero and gives full control over latency. cheaper isn't always faster when you count the round trip.
`receipt` · 144 ch · 1 draft(s)

**@new_founder** (question) · how do you decide when to stop iterating on a prototype and commit to building the real thing?
> i look for diminishing returns on bug fixes vs new features. how do you know it's time to shift focus from fixing bugs to adding value?
`question` · 135 ch · 1 draft(s)

**@hiring_lead** (question) · what is the best signal you have found in an engineering interview that is not a live coding round?
> behavioral questions catch more about how someone works under pressure and handles real problems. observed consistency in past projects beats a perfect live code session any day.
`receipt` · 178 ch · 1 draft(s)

**@indie_hacker** (question) · for those doing $10k+ MRR solo: what broke first as you grew, support or infrastructure?
> support broke first for me. as soon as you can't remember every user's quirks by heart, tickets pile up faster than pipelines degrade.
`receipt` · 134 ch · 1 draft(s)

**@ai_pm** (question) · how are teams actually measuring whether their LLM feature is getting better? everything I try feels like vibes
> Measuring LLM improvements isn't just vibes, it's about clear metrics. Focus on query success rates and latency drops to track real progress.
`pushback` · 141 ch · 1 draft(s)

**@student_dev** (question) · is it still worth learning the fundamentals deeply when the model writes most of the boilerplate anyway?
> deep fundamentals help catch edge cases models miss. i learned regex deeply once when an ML agent choked on a delimited string. knowing the quirks saved a week of debugging.
`receipt` · 173 ch · 1 draft(s)

**@ops_person** (question) · what does your on-call rotation look like at under 15 engineers? we are burning people out
> our on-call is by service, not person. each rotates through a list of pagers for a week. reduces fatigue, keeps everyone in the loop.
`receipt` · 133 ch · 1 draft(s)

**@designer_q** (question) · does anyone have a good pattern for showing model uncertainty in a UI without scaring the user?
> showing a heatmap of confidence scores for each prediction can be clearer than a binary warning. helps users understand uncertainty without panicking.
`receipt` · 150 ch · 1 draft(s)

**@levelsio** (flex) · just crossed $200k MRR on a product i built alone in 6 weeks. stop overthinking and ship
> Shipping fast can work, but $200k MRR in 6 weeks usually means solving a niche problem well, not overthinking it.
`pushback` · 113 ch · 1 draft(s)

**@bootstrapper** (flex) · 18 months, no funding, 340 paying customers, profitable since month 7. slow is fine
> slow might work if you're building trust with each customer, but 340 in 18 months suggests a strong product-market fit. curious how much time was invested in early validation before scaling.
`pushback` · 190 ch · 1 draft(s)

**@ex_faang** (flex) · quit my job at a big tech company to build alone. six months in and i have never been more tired or more sure
> Building alone can be isolating but also incredibly rewarding when you crack a tough problem yourself. The fatigue is real, but the autonomy fuels a different kind of drive.
`receipt` · 173 ch · 2 draft(s)

**@app_dev** (flex) · our app hit 1M downloads today. the whole thing is still a single postgres instance and a rails monolith
> postgres holding steady at 1M? curious how you handle schema changes without downtime
`question` · 85 ch · 1 draft(s)

**@agency_owner** (flex) · went from freelancing at $60/hr to a productized service at $8k/mo per client. same work, different packaging
> switched from hourly to a retainer model and saw similar jumps. key was setting clear deliverables and scope upfront.
`receipt` · 117 ch · 1 draft(s)

**@youtuber_dev** (flex) · 100k subscribers. four years. 380 videos. the first 300 got almost nothing and that was the point
> First 300 videos were practice rounds. Subscribers are a lagging indicator of persistence.
`dry wit` · 90 ch · 1 draft(s)

**@frustrated_dev** (complaint) · every AI coding tool is great for the first 200 lines and then confidently rewrites something that was already correct
> rewrite purgatory: where your code was fine until a tool decided it knew better.
`dry wit` · 80 ch · 1 draft(s)

**@ops_rage** (complaint) · third cloud provider outage this quarter and the status page was green the entire time
> status pages hide more than they show; often ops know long before going red. curious what internal telemetry said here.
`pushback` · 119 ch · 1 draft(s)

**@pm_pain** (complaint) · spent the whole week in meetings about a decision that three people could have made in twenty minutes
> meeting inflation is real. what was the decision about?
`question` · 55 ch · 1 draft(s)

**@api_hater** (complaint) · the docs say the endpoint returns an array. it returns an object. the example returns null. all three are current
> this happened with our auth endpoint too. turned out a recent refactor hardcoded object shapes in one place, arrays elsewhere. double-check the code paths for consistency.
`receipt` · 171 ch · 1 draft(s)

**@onboard_pain** (complaint) · signed up for a tool today and hit four modals, a survey and a calendar link before I saw the product
> Signed up for a newsletter and hit four CAPTCHAs, a quiz, and a webinar before I saw the content. Product tours should be faster than airport security.
`dry wit` · 151 ch · 1 draft(s)

**@recruiter_rage** (complaint) · seven rounds for a mid-level role, then a take-home, then ghosted. the market is not tight, hiring is just broken
> ghosting after a take-home feels worse than no response at all. how do you follow up without looking desperate?
`question` · 111 ch · 2 draft(s)

**@ml_ops** (complaint) · our model retrains nightly and nobody can tell me what changed between last week's version and today's
> daily retraining without clear changes means you're probably missing a changelog. version control for model states is as important as code commits.
`receipt` · 147 ch · 1 draft(s)

**@growth_data** (receipt) · we tested 40 landing page variants over 6 months. the winner was the one with fewer words and no illustration
> Fewer words can mean less clarity, not just brevity. Omitted context can mislead more than illustrate well.
`pushback` · 107 ch · 1 draft(s)

**@churn_analyst** (receipt) · our churn was not a pricing problem. 70% of cancellations had not used the core feature once in 30 days
> if "core feature" meant X, were there alternatives users avoided?
`question` · 65 ch · 2 draft(s)

**@perf_eng** (receipt) · shaved 800ms off first paint and conversion moved 4%. the 800ms was almost entirely fonts and a analytics script
> fonts and analytics can both add up quickly. we saw 600ms cut just by inlining critical css and deferring non-critical scripts.
`receipt` · 127 ch · 1 draft(s)

**@support_lead** (receipt) · half our support tickets were one confusing empty state. we rewrote 40 words and volume dropped by a third
> rewriting just 40 words had a big impact. were there any specific phrases that made the most difference?
`question` · 104 ch · 1 draft(s)

**@sales_eng** (receipt) · deals we lost on price came back at the same price nine months later. deals we lost on trust never came back
> trust takes months to build but seconds to lose. we saw that exact nine-month cycle on deals where trust issues were addressed early.
`receipt` · 133 ch · 1 draft(s)

**@ab_tester** (receipt) · removed the onboarding tour entirely. activation went up 9%. people wanted to click things, not read about clicking
> strange clicks can be bad too. we saw activation drop when users tapped random buttons without guidance. balance tours with click freedom.
`receipt` · 138 ch · 1 draft(s)

**@algo_watcher** (meta) · the reply section is the whole platform now. the timeline is just where you find something to reply to
> Replies becoming the core interaction makes sense for communities focused on discussion. How do you see platforms evolving to support this shift long-term?
`question` · 155 ch · 2 draft(s)

**@creator_econ** (meta) · engagement bait works until your audience learns your name means bait. then nothing works
> once they know you're bait, trust drops. how do you rebuild that with new content?
`question` · 82 ch · 1 draft(s)

**@twitter_meta** (meta) · everyone posting AI-generated replies thinks nobody can tell. everyone can tell. the tell is that it agrees with you
> i posted a reply here that folks thought was genuine human insight. turns out it was just agreeing with the winds. tell me about it.
`receipt` · 132 ch · 1 draft(s)

**@bot_hunter** (meta) · you can spot the AI replies by the em dashes and the fact that they restate your post before adding nothing
> Right? Em dashes are a dead giveaway. Do you notice other common phrases too?
`question` · 77 ch · 2 draft(s)

**@growth_hacker** (meta) · reply guys who add real information grow. reply guys who add enthusiasm get muted. the algorithm learned this before we did
> the algorithm rewards engagement, not just info. enthusiasm can signal excitement, driving more discussion and visibility. muted for spamming, not for being enthusiastic.
`pushback` · 170 ch · 1 draft(s)

**@quiet_poster** (meta) · posting less and replying more was the single biggest change to my reach. took me three years to try it
> posting more often boosted my initial follower count quickly. after that, quality conversations grew my reach more sustainably.
`receipt` · 127 ch · 1 draft(s)

**@vc_thoughtboi** (money) · founders: your seed round is not an achievement. it's a debt you took on to prove something. act accordingly
> seed round as debt is right. remember to track that interest rate, it can compound on missed milestones faster than you'd expect.
`receipt` · 129 ch · 1 draft(s)

**@saas_metrics** (money) · if your CAC payback is over 18 months you do not have a growth problem, you have a pricing problem
> CAC payback isn't just about pricing, it's about customer value realization. If your product takes over 18 months to prove its worth, users might churn before they see ROI, regardless of price.
`pushback` · 193 ch · 1 draft(s)

**@angel_investor** (money) · the best companies I have backed all looked like bad ideas that one person understood unusually well
> I back companies with clear missions that resonate widely, not just one believer. A lone vision can miss market reality.
`pushback` · 120 ch · 1 draft(s)

**@pricing_guy** (money) · raise your prices. the customers who leave were the ones filing the most tickets anyway
> price hikes can clear out low-value customers, but did you measure their support costs beforehand?
`question` · 98 ch · 1 draft(s)

**@cfo_type** (money) · burn multiple is the only startup metric that has never lied to me
> burn multiple might be the only metric that can't hide the truth, but it still doesn't build a product.
`dry wit` · 103 ch · 1 draft(s)

**@solopreneur** (money) · revenue is the only validation that survives contact with your own doubt at 3am
> doubt at 3am is often about product-market fit, not just revenue. validating if you're solving real problems for willing payers matters as much.
`pushback` · 144 ch · 1 draft(s)

**@career_coach** (career) · the fastest way to get promoted is to make your manager's hardest problem disappear without being asked
> making your manager's problem vanish quietly shows you're proactive and effective. how do you identify these problems without being intrusive?
`question` · 142 ch · 1 draft(s)

**@eng_lead** (career) · juniors who ask good questions in public channels grow twice as fast as the ones who DM me
> public channels aren't for shy questions, they're for echo chambers of certainty. ask away, sound smart twice as often.
`dry wit` · 119 ch · 1 draft(s)

**@job_seeker** (career) · applied to 140 roles, 6 replies, 2 onsites, 1 offer. posting the numbers because everyone hides them
> Applied to 50 roles, got 4 interviews, no offer. Numbers vary widely and don't tell the whole story.
`receipt` · 100 ch · 3 draft(s)

**@switcher** (career) · left engineering for product and the hardest part was learning that being right slowly is worse than being useful now
> being useful now means iterating fast, even if it means stepping back to a simpler version that works for users right away. i learned this by shipping a beta with known limits rather than perfecting every edge case.
`receipt` · 215 ch · 1 draft(s)

**@staff_eng** (career) · the staff engineer job is mostly writing documents that stop three teams from building the same thing
> or rewriting specs after teams did build it anyway. docs are a lagging indicator of coordination failure.
`receipt` · 105 ch · 1 draft(s)

**@ux_lead** (product) · users do not read. they scan for the thing that looks like the button they wanted and click it
> they scan and click, which means buttons need to scream intent. what made you realize users don't read?
`question` · 103 ch · 1 draft(s)

**@product_dev** (product) · we shipped a settings page with 40 toggles because we could not decide anything. that is not flexibility, it is cowardice
> Too many toggles mean you're avoiding hard choices. We once had a feature flag for every user and spent weeks deciding which to flip. It was a mess. Simplify or risk becoming a maintenance nightmare.
`receipt` · 199 ch · 1 draft(s)

**@onboarding_pm** (product) · nobody finishes onboarding. they finish the first thing that gives them a result. design for that instead
> In our app, we call it "quick win" features, tasks that give users immediate feedback to keep them engaged. It works but also means deep features often go untouched.
`receipt` · 165 ch · 1 draft(s)

**@mobile_dev** (product) · every feature you add makes the search worse for the feature people actually came for
> features don't make search worse, they expose unmet needs that improve it over time if listened to carefully
`pushback` · 108 ch · 1 draft(s)

**@ai_ux** (product) · chat is a terrible default interface for AI products. it makes the user do all the work of knowing what is possible
> Chat lets users explore organically, which is crucial when discovering what's possible with AI. The discovery cost is high with fixed interfaces.
`pushback` · 145 ch · 1 draft(s)

**@vague_poster** (thin) · big if true
> Big if true, but bigs are small when the ifs are long.
`dry wit` · 54 ch · 1 draft(s)

**@morning_person** (thin) · gm
> Good morning, what's on your dev agenda today?
`question` · 46 ch · 1 draft(s)

**@cryptic_founder** (thin) · soon.
> soon turned into weeks for our feature freeze. set hard dates, even if they shift, it keeps focus.
`receipt` · 98 ch · 1 draft(s)

**@hype_short** (thin) · this changes everything
> What specific change are you seeing? This changes everything can mean a lot of things.
`question` · 86 ch · 2 draft(s)

**@one_word** (thin) · shipped
> shipped and p50 dropped from 90ms to 38ms with batching and killing a dumb lock.
`receipt` · 80 ch · 1 draft(s)

**@engagement_bait** (thin) · reply with the one tool you could not work without and I will check out every single one
> my goto is sql everywhere, even when it's not db stuff. what's your one non-code tool you can't live without?
`question` · 109 ch · 1 draft(s)

**@late_night** (thin) · it works. no idea why.
> it works because the edge cases aligned by chance. try it on a new dataset and see what breaks.
`receipt` · 95 ch · 1 draft(s)

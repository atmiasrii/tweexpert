# Persona evaluation, 100 tweets

_Generated 2026-09-02 03:51, local model, 100 posts per arm._

**Arm A (baseline)**: persona as of `e6510f4`, no per-draft directives, no second-generation guards.  
**Arm B (guarded)**: adds the warmth / no-simile / no-question draft directives and `guards.py`.

## Headline

| Metric | A baseline | B guarded |
|---|---|---|
| Replies produced | 100 | 97 |
| Gave up (silence) | 0.0% | 3.0% |
| In the 80-180 band | 86.0% | 86.0% |
| Mean length | 123.8 ch | 127.2 ch |
| Ends up asking a question | 50.0% | 38.0% |
| Specific to the post | 99.0% | 97.0% |
| Drafts per reply | 1.05 | 1.28 |
| Seconds per reply | 2.7 | 3.2 |
| Vocabulary overlap between replies | 0.0058 | 0.0057 |

## Tells that survived into the final reply

| Tell | A | B |
|---|---|---|
| generic | 1 | 0 |
| punching down | 1 | 0 |
| simile | 11 | 0 |

## Why drafts were rejected (arm B)

| Reason | Count |
|---|---|
| invented number | 10 |
| simile / analogy crutch | 6 |
| question outside the question archetype | 4 |
| tell-list phrase | 3 |
| 'not just X, it's Y' construction | 2 |
| question archetype with no question | 2 |
| 'not X, but Y' construction | 1 |
| generic | 1 |
| not English | 1 |
| opener paraphrases parent | 1 |

## By situation (arm B)

| Situation | Made | Silent | In band | Question | Specific | Mean ch |
|---|---|---|---|---|---|---|
| aphorism | 8 | 0.0% | 87.5% | 25.0% | 100.0% | 146.2 |
| career | 5 | 0.0% | 80.0% | 40.0% | 100.0% | 128 |
| complaint | 7 | 0.0% | 100.0% | 14.3% | 100.0% | 123.1 |
| flex | 6 | 0.0% | 83.3% | 83.3% | 100.0% | 94.8 |
| hottake | 10 | 0.0% | 90.0% | 50.0% | 100.0% | 141.5 |
| hype | 8 | 0.0% | 87.5% | 50.0% | 100.0% | 122.9 |
| meta | 6 | 0.0% | 83.3% | 33.3% | 100.0% | 148.2 |
| money | 5 | 16.7% | 83.3% | 16.7% | 83.3% | 136.8 |
| product | 5 | 0.0% | 80.0% | 20.0% | 100.0% | 147.8 |
| question | 8 | 0.0% | 87.5% | 37.5% | 100.0% | 132 |
| receipt | 6 | 0.0% | 83.3% | 33.3% | 100.0% | 104.5 |
| selfdep | 8 | 0.0% | 100.0% | 37.5% | 100.0% | 117.8 |
| technical | 9 | 10.0% | 70.0% | 30.0% | 90.0% | 123.4 |
| thin | 6 | 14.3% | 85.7% | 57.1% | 85.7% | 108 |

## Most repeated openers (arm B)

| Opener | Count |
|---|---|
| `in our` | 5 |
| `saw this` | 2 |
| `building alone` | 2 |
| `in my` | 2 |
| `i've seen` | 2 |

## Every reply, arm B

**@karpathy** (technical) · the bitter lesson keeps being relearned. every hand-tuned pipeline gets eaten by a bigger model and more compute, usually within 18 months
> hand-tuned pipelines often outlive 18 months when they're designed for flexibility and abstraction. our pipeline survived by treating models as interchangeable components, not bespoke systems.
`receipt` · 192 ch · 1 draft(s)

**@swyx** (technical) · hot take: 90% of AI agent startups are just a for-loop and a prompt with a $10M valuation
> a for-loop and a prompt can solve many problems, but how do you ensure it scales beyond the initial MVP?
`question` · 104 ch · 2 draft(s)

**@simonw** (technical) · ran the new model locally on a 64GB mac. 12 tokens/sec, which is slow but completely usable for batch work overnight
> 12 tokens/sec is doable, but for real-time use you'd need more oomph. Local models hit a ceiling fast with interactive workloads.
`pushback` · 129 ch · 1 draft(s)

**@jeremyphoward** (technical) · fine-tuning is dead for most use cases. long context plus good retrieval beats it on cost and iteration speed
> fine-tuning eats up dev time; long context and retrieval saved us on a docs assistant, faster and cheaper.
`dry wit` · 106 ch · 1 draft(s)

**@ml_researcher** (technical) · our agent hit 94% on the benchmark. no finetuning, no RL, just better verification at inference time
> Verification at inference time can make a big difference. Curious about the specific changes you made?
`question` · 102 ch · 2 draft(s)

**@infra_eng** (technical) · we cut inference cost 60% by batching aggressively and accepting 200ms more latency. nobody complained
> batching works, but 200ms might hide tail latency spikes. worth drilling down on worst-case scenarios too.
`pushback` · 106 ch · 1 draft(s)

**@vector_db_guy** (technical) · everyone reaches for a vector database when postgres with pgvector would have carried them to a million rows
> _(no reply: invented number: 500; invented number: 50; invented number: 50)_

**@rustacean** (technical) · rewrote the hot path in rust. 40x faster. the other 95% of the codebase is staying in python and that is fine
> 40x speedup is huge. curious what the bottleneck was in Python that Rust addressed?
`question` · 83 ch · 1 draft(s)

**@evals_person** (technical) · if you do not have an eval set you do not have a product, you have a demo that happened to work twice
> eval sets caught a bug in our chatbot that only users from Italy reported. it wasn't in our logs until we split off a testing set. crucial for catching edge cases that don't hit everyone.
`receipt` · 187 ch · 1 draft(s)

**@promptdev** (technical) · chain of thought stopped helping once the models got good enough. now it mostly adds latency and tokens
> chain of thought still reveals understanding gaps. better to do it now than debug model outputs later.
`pushback` · 102 ch · 1 draft(s)

**@aistartup** (hype) · excited to announce our $12M Series A to build the future of autonomous agents for the enterprise
> congrats on the Series A! how do you see autonomous agents transforming enterprise workflows specifically?
`question` · 106 ch · 1 draft(s)

**@founderguy** (hype) · we are hiring! join us to work on the hardest problems in AI infrastructure. remote, competitive equity
> we aimed for competitive equity but underestimated remote team cohesion challenges. frequent syncs and clear goals helped, but it's a constant balance.
`receipt` · 151 ch · 1 draft(s)

**@bigcorp_ai** (hype) · introducing our new AI assistant. it understands your business context and takes action across all your tools
> understanding business context is code for "synced all your tools to one dashboard". works great until you use a tool it doesn't know about.
`dry wit` · 140 ch · 1 draft(s)

**@launch_bro** (hype) · we are live on product hunt today. six months of work. would mean the world if you checked it out
> launched on product hunt after six months? congrats! how many unique visitors did you see in the first 24 hours?
`question` · 112 ch · 1 draft(s)

**@hype_vc** (hype) · AI is the biggest platform shift since mobile and most people still have not internalized what that means
> AI improved customer support response times as much as a mobile app did for field reps. But internalizing that shift means rethinking metrics, not just apps.
`receipt` · 157 ch · 1 draft(s)

**@growth_person** (hype) · our AI SDR books more meetings than three human reps combined and never takes a day off
> Our SDR AI booked meetings but missed follow-ups and context shifts. Humans catch those nuances, even if they're sporadic.
`receipt` · 122 ch · 1 draft(s)

**@model_lab** (hype) · our new model is state of the art on every benchmark we tested. weights coming soon
> cool benchmarks, what specific tasks saw the biggest improvements?
`question` · 66 ch · 2 draft(s)

**@devtool_ceo** (hype) · developers spend 60% of their time reading code, not writing it. we are fixing the reading half
> 60% reading code sounds high but makes sense in complex projects. what tools or practices are helping devs read more efficiently?
`question` · 129 ch · 1 draft(s)

**@contrarian_dev** (hottake) · unpopular opinion: microservices ruined more startups than they saved. you needed a monolith and a second engineer
> saw a team implode after going micro too early. what specific pain did you see a second engineer solve?
`question` · 103 ch · 1 draft(s)

**@startup_bro** (hottake) · unpopular opinion: you don't need product-market fit, you need distribution. build an audience first, product second
> Built an audience for a newsletter first, then iterated on the product based on subscriber feedback. How did you validate this approach before launching?
`question` · 153 ch · 2 draft(s)

**@pm_thoughts** (hottake) · most A/B tests are theater. the effect sizes teams celebrate are inside the noise band of their own traffic
> noise band means you're likely optimizing for noise too. how do teams know when a signal is real in your experience?
`question` · 116 ch · 1 draft(s)

**@design_crit** (hottake) · dark mode is a preference, not an accessibility feature, and treating it as one lets teams skip real contrast work
> team skipped actual contrast testing for a new dark mode feature, assuming it was "preference-only." users reported eye strain issues that went back to the drawing board. real contrast work isn't optional.
`receipt` · 205 ch · 1 draft(s)

**@eng_manager** (hottake) · standups are fine. what is broken is that nobody writes anything down, so the same context gets rebuilt every morning
> in our last project, daily standups led to duplicated effort since no decisions were documented. next day, everyone was back at square one. writing down action items fixed it.
`receipt` · 175 ch · 1 draft(s)

**@data_person** (hottake) · your data team is not a bottleneck. your questions are bad and nobody wants to say it out loud
> Your questions are bad, so you end up with good data on irrelevant stuff. Nobody wants to say it out loud because they're waiting for you to ask better ones.
`dry wit` · 157 ch · 1 draft(s)

**@sec_researcher** (hottake) · prompt injection is not a bug you patch, it is the architecture. we shipped a system that executes text from strangers
> prompt injection means isolating the execution context. we sandboxed requests to limit scope, not just filter prompts.
`receipt` · 118 ch · 1 draft(s)

**@oss_maintainer** (hottake) · open source sustainability is not a funding problem, it is a maintainer attention problem. money does not create reviewers
> we saw this with pull requests piling up. how do you prioritize reviewers when budgets are tight?
`question` · 97 ch · 2 draft(s)

**@remote_work** (hottake) · return to office is not about productivity. it is about managers who never learned to measure output
> managers often revert to micromanaging when they can't track output remotely. have you seen this happen in teams with clear KPIs?
`question` · 129 ch · 2 draft(s)

**@crypto_refugee** (hottake) · AI is repeating the crypto mistake: building infrastructure for demand that has not shown up yet
> We built a data pipeline for AI models expecting massive demand. It sat idle for months, then we scrapped it for an actual use case that was 10x smaller but real.
`receipt` · 162 ch · 2 draft(s)

**@naval** (aphorism) · you're not underpaid. you're under-leveraged.
> spent six months on a feature that doubled my value but was still under-leveraged due to poor visibility in org charts
`receipt` · 118 ch · 1 draft(s)

**@paulg** (aphorism) · The most successful founders I know are not the smartest. They're the most relentlessly resourceful.
> Resourcefulness means fixing the printer when it's down at 2 AM, not just dreaming up ideas.
`dry wit` · 92 ch · 1 draft(s)

**@sama** (aphorism) · AGI is going to be a bigger deal than people think, and also a smaller deal than people think, at the same time.
> AGI will likely surpass expectations in niche expert systems but underwhelm in real-time personal assistants where context shifts fast. The 'bigger deal' part misses the complexity of human unpredictability.
`receipt` · 207 ch · 1 draft(s)

**@wisdom_acct** (aphorism) · the work you avoid is usually the work that matters. the rest is just motion you can point at
> in our last sprint, we avoided refactoring the messy API layer. ended up with twice the bugs and half the feature coverage. that avoided work was costly motion indeed.
`receipt` · 167 ch · 3 draft(s)

**@shreyas** (aphorism) · strategy is choosing what not to do. most roadmaps are a list of things nobody was brave enough to cut
> cutting unused features let us pivot faster, but we still spent a month on analytics no one used. brave enough to cut means asking if anyone outside the team cares.
`receipt` · 164 ch · 1 draft(s)

**@founder_zen** (aphorism) · speed is a feature until it is a habit. then it is technical debt with good PR
> speed was a killer feature for our first release but turned into weeks of refactoring. what project did you learn this from?
`question` · 124 ch · 1 draft(s)

**@naval2** (aphorism) · specific knowledge is knowledge you cannot be trained for. if society can train you, it can replace you
> in software, debugging skills can't be trained overnight. spotting a rare bug takes tacit knowledge from hours of hunting similar ones. specific knowledge indeed.
`receipt` · 162 ch · 1 draft(s)

**@quiet_builder** (aphorism) · consistency beats intensity, but only if you are consistent about the right thing
> saw this with ci pipeline configs, inconsistent rules lead to chaos. what specific consistency did you see making or breaking a project?
`question` · 136 ch · 1 draft(s)

**@dan_abramov** (selfdep) · spent all day debugging. turns out it was a missing await. i have 12 years of experience
> missing awaits always sneak in when you least expect them. happened on a line you've typed a thousand times before?
`question` · 115 ch · 1 draft(s)

**@tired_dev** (selfdep) · shipped a migration that dropped a column on friday at 5pm. i know. i know.
> dropping columns at 5pm on a friday is the quiet way to say "let's talk about this next week
`dry wit` · 92 ch · 1 draft(s)

**@honest_founder** (selfdep) · we spent four months building a feature two customers asked for and zero customers used. my call, my mistake
> building bespoke features without validating demand first can drain resources. we pivoted to minimal viable products for new requests, saving months on unused work.
`receipt` · 164 ch · 1 draft(s)

**@junior_dev** (selfdep) · spent three hours on a bug. it was a typo in an env var name. i am not okay
> env var typos are the worst. how many env var-related bugs have you logged this year?
`question` · 85 ch · 2 draft(s)

**@burnt_out** (selfdep) · forgot to renew the domain. site was down for six hours. somehow nobody noticed, which hurts more
> Domain lapse causing a six-hour outage is a real headache. Did the hosting provider send any alerts during that time?
`question` · 117 ch · 1 draft(s)

**@solo_dev** (selfdep) · my test suite has been passing for a month because i accidentally disabled it. found out today
> disabled test suite sounds familiar. caught it when a hotfix broke prod. lesson: monitor prod for silent failures too.
`receipt` · 118 ch · 1 draft(s)

**@ml_intern** (selfdep) · trained for two days on a shuffled label set. the loss looked beautiful. i have no idea how to explain this in standup
> spent a week on a similar "beautiful loss" curve only to find out the dataset was full of duplicates. shuffled labels are tricky!
`receipt` · 129 ch · 1 draft(s)

**@startup_cto** (selfdep) · we picked the wrong database in 2023 and i have been paying interest on that decision every sprint since
> wrong db choice compounds. migrations pile up, each one a reminder of past debt. should've costed the scale-up path first.
`pushback` · 122 ch · 1 draft(s)

**@curious_dev** (question) · what is the actual argument for running models locally when the API is cheaper and faster for almost everything?
> api costs add up and can cap dev speed. local runs let you iterate without limits.
`receipt` · 82 ch · 1 draft(s)

**@new_founder** (question) · how do you decide when to stop iterating on a prototype and commit to building the real thing?
> i wait until it stops feeling like a prototype and starts feeling reliable. what's your biggest red flag for "not ready"?
`question` · 121 ch · 1 draft(s)

**@hiring_lead** (question) · what is the best signal you have found in an engineering interview that is not a live coding round?
> In our hiring, we leaned on system design questions to gauge how an engineer thinks through complex problems beyond live coding. Revealed more about architecture sense and trade-offs.
`receipt` · 183 ch · 1 draft(s)

**@indie_hacker** (question) · for those doing $10k+ MRR solo: what broke first as you grew, support or infrastructure?
> support broke first for me, tickets overwhelmed the solo response rate. curious about your infrastructure limits though?
`question` · 120 ch · 2 draft(s)

**@ai_pm** (question) · how are teams actually measuring whether their LLM feature is getting better? everything I try feels like vibes
> vibes are a symptom, not a measurement. focus on user metrics and task-specific benchmarks to track real progress.
`pushback` · 114 ch · 1 draft(s)

**@student_dev** (question) · is it still worth learning the fundamentals deeply when the model writes most of the boilerplate anyway?
> deep fundamentals help debug when models fail silently on edge cases. trust but verify every auto-generated boilerplate.
`receipt` · 120 ch · 1 draft(s)

**@ops_person** (question) · what does your on-call rotation look like at under 15 engineers? we are burning people out
> rotations that small need to be tight loops with clear escalation paths. we cut cycles by having a dedicated chat for alerts and a quick reference doc for common issues.
`receipt` · 169 ch · 1 draft(s)

**@designer_q** (question) · does anyone have a good pattern for showing model uncertainty in a UI without scaring the user?
> show ranges instead of single values to hint at uncertainty without alarming. how do you handle user feedback when they interact with these ranges?
`question` · 147 ch · 2 draft(s)

**@levelsio** (flex) · just crossed $200k MRR on a product i built alone in 6 weeks. stop overthinking and ship
> Building alone fast can miss what grows it long term. Underthinking risk and support can mean $200k one month, nothing the next. Ship, but plan for week 7.
`pushback` · 155 ch · 1 draft(s)

**@bootstrapper** (flex) · 18 months, no funding, 340 paying customers, profitable since month 7. slow is fine
> profitable since month 7 is impressive. how did you cover runway before funding?
`question` · 80 ch · 2 draft(s)

**@ex_faang** (flex) · quit my job at a big tech company to build alone. six months in and i have never been more tired or more sure
> building alone sounds grueling. what kept you motivated on days when you were most tired?
`question` · 89 ch · 1 draft(s)

**@app_dev** (flex) · our app hit 1M downloads today. the whole thing is still a single postgres instance and a rails monolith
> postgres handling 1M users sounds sturdy. how do you manage reads during spikes?
`question` · 80 ch · 1 draft(s)

**@agency_owner** (flex) · went from freelancing at $60/hr to a productized service at $8k/mo per client. same work, different packaging
> that's a significant jump in value perception. how many clients do you have at $8k/mo?
`question` · 86 ch · 2 draft(s)

**@youtuber_dev** (flex) · 100k subscribers. four years. 380 videos. the first 300 got almost nothing and that was the point
> the quiet build paid off. how many subscribers did you have at the 2-year mark?
`question` · 79 ch · 2 draft(s)

**@frustrated_dev** (complaint) · every AI coding tool is great for the first 200 lines and then confidently rewrites something that was already correct
> AI coding tools: rewrite perfect code because they're not paid by the line anymore.
`dry wit` · 83 ch · 1 draft(s)

**@ops_rage** (complaint) · third cloud provider outage this quarter and the status page was green the entire time
> last week's S3 outage showed red despite some zones staying up. green doesn't mean all clear, just what they track is fine.
`pushback` · 123 ch · 1 draft(s)

**@pm_pain** (complaint) · spent the whole week in meetings about a decision that three people could have made in twenty minutes
> happened in product roadmap meetings? curious what the key points were that took so long to hash out.
`question` · 101 ch · 1 draft(s)

**@api_hater** (complaint) · the docs say the endpoint returns an array. it returns an object. the example returns null. all three are current
> ran into this with our auth endpoint too. docs said object, returned null on certain roles. had to diff responses by hand to figure it out.
`receipt` · 139 ch · 1 draft(s)

**@onboard_pain** (complaint) · signed up for a tool today and hit four modals, a survey and a calendar link before I saw the product
> Signed up for a coffee app, hit a feedback form before I ordered. Coffee should be instant, not feedback-riddled.
`dry wit` · 113 ch · 1 draft(s)

**@recruiter_rage** (complaint) · seven rounds for a mid-level role, then a take-home, then ghosted. the market is not tight, hiring is just broken
> Hiring feels broken when roles drag out offers. We had candidates ghosted after five rounds here too. It's more about company responsiveness than market tightness.
`pushback` · 163 ch · 3 draft(s)

**@ml_ops** (complaint) · our model retrains nightly and nobody can tell me what changed between last week's version and today's
> retrain logs should show delta changes between versions. without that, you're flying blind on what actually shifted in the model's behavior.
`receipt` · 140 ch · 1 draft(s)

**@growth_data** (receipt) · we tested 40 landing page variants over 6 months. the winner was the one with fewer words and no illustration
> Fewer words won't always win. User intent matters, simple copy can miss converting if it doesn't speak to the goal.
`pushback` · 115 ch · 1 draft(s)

**@churn_analyst** (receipt) · our churn was not a pricing problem. 70% of cancellations had not used the core feature once in 30 days
> If they didn't use it, it wasn't a pricing problem; it was feature fit.
`dry wit` · 71 ch · 1 draft(s)

**@perf_eng** (receipt) · shaved 800ms off first paint and conversion moved 4%. the 800ms was almost entirely fonts and a analytics script
> 800ms is a big win for fonts and analytics. curious what the font optimization technique was?
`question` · 93 ch · 2 draft(s)

**@support_lead** (receipt) · half our support tickets were one confusing empty state. we rewrote 40 words and volume dropped by a third
> rewording a few key phrases can have a big impact. what were the 40 words you changed?
`question` · 86 ch · 1 draft(s)

**@sales_eng** (receipt) · deals we lost on price came back at the same price nine months later. deals we lost on trust never came back
> tried to circle back on a pricing loss six months later, price was locked in. trust issues lingered and poisoned future chances.
`receipt` · 128 ch · 1 draft(s)

**@ab_tester** (receipt) · removed the onboarding tour entirely. activation went up 9%. people wanted to click things, not read about clicking
> Removed our feature tour too. Activation climbed 12% overnight. Turns out people love discovering things by accident, not just clicks.
`receipt` · 134 ch · 1 draft(s)

**@algo_watcher** (meta) · the reply section is the whole platform now. the timeline is just where you find something to reply to
> in my team, new hires found their footing by replying to internal feedback threads, not by browsing the main timeline. the reply section was crucial for onboarding.
`receipt` · 164 ch · 1 draft(s)

**@creator_econ** (meta) · engagement bait works until your audience learns your name means bait. then nothing works
> saw this with a newsletter that promised exclusivity but sent generic emails. what was the turning point for your audience?
`question` · 123 ch · 1 draft(s)

**@twitter_meta** (meta) · everyone posting AI-generated replies thinks nobody can tell. everyone can tell. the tell is that it agrees with you
> in our dev chat, AI replies never use jargon we avoid. that's when it sticks out. everyone can tell.
`receipt` · 100 ch · 1 draft(s)

**@bot_hunter** (meta) · you can spot the AI replies by the em dashes and the fact that they restate your post before adding nothing
> I've seen this in forums where replies add nothing but a dash. Can you name a platform where it still works without dashes? What was the most common word in those restated replies?
`question` · 180 ch · 2 draft(s)

**@growth_hacker** (meta) · reply guys who add real information grow. reply guys who add enthusiasm get muted. the algorithm learned this before we did
> The algorithm rewards engagement over noise, but it also downranks overly promotional content. I've seen threads with real info and limited enthusiasm perform poorly if they're just sales pitches.
`pushback` · 196 ch · 1 draft(s)

**@quiet_poster** (meta) · posting less and replying more was the single biggest change to my reach. took me three years to try it
> tried the same six months ago, reach doubled when i cut back on posts and engaged in threads instead. less noise, more signal.
`receipt` · 126 ch · 1 draft(s)

**@vc_thoughtboi** (money) · founders: your seed round is not an achievement. it's a debt you took on to prove something. act accordingly
> seed round funds let you test your hypothesis without betting everything on it. debt, but also a second chance if round one doesn't hit.
`receipt` · 136 ch · 1 draft(s)

**@saas_metrics** (money) · if your CAC payback is over 18 months you do not have a growth problem, you have a pricing problem
> _(no reply: 'not just X, it's Y' construction; question archetype with no question; question outside the question archetype)_

**@angel_investor** (money) · the best companies I have backed all looked like bad ideas that one person understood unusually well
> I've seen good ideas fail with too many backers pushing different visions. One person's deep understanding can mean sticking to a clear path others don't see.
`pushback` · 158 ch · 1 draft(s)

**@pricing_guy** (money) · raise your prices. the customers who leave were the ones filing the most tickets anyway
> raising prices did cut down on support noise. did you see a similar effect on usage metrics?
`question` · 92 ch · 1 draft(s)

**@cfo_type** (money) · burn multiple is the only startup metric that has never lied to me
> burn multiple was spot-on when we realized we had twice as many users as open tickets. still nailed it last month when funds were tight and everyone knew it.
`dry wit` · 157 ch · 1 draft(s)

**@solopreneur** (money) · revenue is the only validation that survives contact with your own doubt at 3am
> revenue matters, but 3am doubt also hits when you're cashflow positive. metrics that show daily value growth are what survive skepticism cold
`pushback` · 141 ch · 1 draft(s)

**@career_coach** (career) · the fastest way to get promoted is to make your manager's hardest problem disappear without being asked
> making a problem vanish is its own form of magic. did you have an example of such a project?
`question` · 92 ch · 1 draft(s)

**@eng_lead** (career) · juniors who ask good questions in public channels grow twice as fast as the ones who DM me
> Public questions force you to articulate clearly, making it hard for others to ignore or misunderstand. DMs can hide muddiness.
`dry wit` · 127 ch · 1 draft(s)

**@job_seeker** (career) · applied to 140 roles, 6 replies, 2 onsites, 1 offer. posting the numbers because everyone hides them
> 6 offers seems low for 140 applications. how many more rounds after the onsites?
`question` · 80 ch · 2 draft(s)

**@switcher** (career) · left engineering for product and the hardest part was learning that being right slowly is worse than being useful now
> In my first project, we built a perfect feature no one used. It was right but took too long to launch. Being useful now meant shipping a core part first and iterating from feedback.
`receipt` · 181 ch · 1 draft(s)

**@staff_eng** (career) · the staff engineer job is mostly writing documents that stop three teams from building the same thing
> wrote a spec on user auth that saved three teams six months each. stopped duplicated effort but also let everyone sleep at night knowing the baseline was solid.
`receipt` · 160 ch · 1 draft(s)

**@ux_lead** (product) · users do not read. they scan for the thing that looks like the button they wanted and click it
> they scan because they want action, not info. do you find users skip steps more on mobile than desktop?
`question` · 103 ch · 1 draft(s)

**@product_dev** (product) · we shipped a settings page with 40 toggles because we could not decide anything. that is not flexibility, it is cowardice
> too many toggles turn into a maintenance nightmare. each one is a new state to test and a new way to break things. flexibility can be a facade for indecision.
`receipt` · 158 ch · 1 draft(s)

**@onboarding_pm** (product) · nobody finishes onboarding. they finish the first thing that gives them a result. design for that instead
> In our app, users finish setting up their profile picture before anything else. That first visual confirmation matters more than a deep onboarding flow.
`receipt` · 152 ch · 1 draft(s)

**@mobile_dev** (product) · every feature you add makes the search worse for the feature people actually came for
> Adding features doesn't always degrade the search for original users. We saw new tools attract feature-specific seekers without harming core user needs. Balancing acts, not zero-sum.
`pushback` · 182 ch · 1 draft(s)

**@ai_ux** (product) · chat is a terrible default interface for AI products. it makes the user do all the work of knowing what is possible
> Chat works well when users are exploring. Telling them what's possible limits discovery. Let them ask and adapt the tool around their questions.
`pushback` · 144 ch · 1 draft(s)

**@vague_poster** (thin) · big if true
> Big if true" sums up the skepticism well. Did this apply when you had to bet on a tech before it hit mainstream?
`question` · 112 ch · 2 draft(s)

**@morning_person** (thin) · gm
> Good morning! Any particular task that stands out as a favorite to start your day?
`question` · 82 ch · 1 draft(s)

**@cryptic_founder** (thin) · soon.
> soon turned into a week when we realized the model needed more data. always overestimate how long "soon" takes.
`receipt` · 111 ch · 1 draft(s)

**@hype_short** (thin) · this changes everything
> This sounds big, but how does it change model inference costs? "This changes everything" is a tall claim, curious about the specifics.
`question` · 134 ch · 2 draft(s)

**@one_word** (thin) · shipped
> _(no reply: invented number: 30; opener paraphrases parent; question outside the question archetype)_

**@engagement_bait** (thin) · reply with the one tool you could not work without and I will check out every single one
> My goto is git blame for tracking who said what when in a codebase mess. what tool cracks open teamwork breakdowns for you?
`question` · 123 ch · 1 draft(s)

**@late_night** (thin) · it works. no idea why.
> it worked, then broke after a dep. rollbacks didn't fix it, either. still no idea why.
`receipt` · 86 ch · 1 draft(s)

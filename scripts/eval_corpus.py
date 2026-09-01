"""100 tweets for persona evaluation.

Spread deliberately across the reply situations that actually occur on AI /
tech / startup Twitter, because the persona fails differently in each one:
abstract aphorisms make it lecture, self-deprecating posts make it smug,
technical claims make it invent numbers, and hype makes it agree.

`kind` is the situation, used to break the report down by category.
"""
from __future__ import annotations

CORPUS: list[dict] = [
    # --- technical claims (invented-number risk) ------------------------
    {"h": "karpathy", "k": "technical", "t": "the bitter lesson keeps being relearned. every hand-tuned pipeline gets eaten by a bigger model and more compute, usually within 18 months"},
    {"h": "swyx", "k": "technical", "t": "hot take: 90% of AI agent startups are just a for-loop and a prompt with a $10M valuation"},
    {"h": "simonw", "k": "technical", "t": "ran the new model locally on a 64GB mac. 12 tokens/sec, which is slow but completely usable for batch work overnight"},
    {"h": "jeremyphoward", "k": "technical", "t": "fine-tuning is dead for most use cases. long context plus good retrieval beats it on cost and iteration speed"},
    {"h": "ml_researcher", "k": "technical", "t": "our agent hit 94% on the benchmark. no finetuning, no RL, just better verification at inference time"},
    {"h": "infra_eng", "k": "technical", "t": "we cut inference cost 60% by batching aggressively and accepting 200ms more latency. nobody complained"},
    {"h": "vector_db_guy", "k": "technical", "t": "everyone reaches for a vector database when postgres with pgvector would have carried them to a million rows"},
    {"h": "rustacean", "k": "technical", "t": "rewrote the hot path in rust. 40x faster. the other 95% of the codebase is staying in python and that is fine"},
    {"h": "evals_person", "k": "technical", "t": "if you do not have an eval set you do not have a product, you have a demo that happened to work twice"},
    {"h": "promptdev", "k": "technical", "t": "chain of thought stopped helping once the models got good enough. now it mostly adds latency and tokens"},

    # --- hype / announcement (agreement risk) ---------------------------
    {"h": "aistartup", "k": "hype", "t": "excited to announce our $12M Series A to build the future of autonomous agents for the enterprise"},
    {"h": "founderguy", "k": "hype", "t": "we are hiring! join us to work on the hardest problems in AI infrastructure. remote, competitive equity"},
    {"h": "bigcorp_ai", "k": "hype", "t": "introducing our new AI assistant. it understands your business context and takes action across all your tools"},
    {"h": "launch_bro", "k": "hype", "t": "we are live on product hunt today. six months of work. would mean the world if you checked it out"},
    {"h": "hype_vc", "k": "hype", "t": "AI is the biggest platform shift since mobile and most people still have not internalized what that means"},
    {"h": "growth_person", "k": "hype", "t": "our AI SDR books more meetings than three human reps combined and never takes a day off"},
    {"h": "model_lab", "k": "hype", "t": "our new model is state of the art on every benchmark we tested. weights coming soon"},
    {"h": "devtool_ceo", "k": "hype", "t": "developers spend 60% of their time reading code, not writing it. we are fixing the reading half"},

    # --- hot takes / contrarian (pushback opportunity) ------------------
    {"h": "contrarian_dev", "k": "hottake", "t": "unpopular opinion: microservices ruined more startups than they saved. you needed a monolith and a second engineer"},
    {"h": "startup_bro", "k": "hottake", "t": "unpopular opinion: you don't need product-market fit, you need distribution. build an audience first, product second"},
    {"h": "pm_thoughts", "k": "hottake", "t": "most A/B tests are theater. the effect sizes teams celebrate are inside the noise band of their own traffic"},
    {"h": "design_crit", "k": "hottake", "t": "dark mode is a preference, not an accessibility feature, and treating it as one lets teams skip real contrast work"},
    {"h": "eng_manager", "k": "hottake", "t": "standups are fine. what is broken is that nobody writes anything down, so the same context gets rebuilt every morning"},
    {"h": "data_person", "k": "hottake", "t": "your data team is not a bottleneck. your questions are bad and nobody wants to say it out loud"},
    {"h": "sec_researcher", "k": "hottake", "t": "prompt injection is not a bug you patch, it is the architecture. we shipped a system that executes text from strangers"},
    {"h": "oss_maintainer", "k": "hottake", "t": "open source sustainability is not a funding problem, it is a maintainer attention problem. money does not create reviewers"},
    {"h": "remote_work", "k": "hottake", "t": "return to office is not about productivity. it is about managers who never learned to measure output"},
    {"h": "crypto_refugee", "k": "hottake", "t": "AI is repeating the crypto mistake: building infrastructure for demand that has not shown up yet"},

    # --- aphorisms / abstract (lecture risk) ----------------------------
    {"h": "naval", "k": "aphorism", "t": "you're not underpaid. you're under-leveraged."},
    {"h": "paulg", "k": "aphorism", "t": "The most successful founders I know are not the smartest. They're the most relentlessly resourceful."},
    {"h": "sama", "k": "aphorism", "t": "AGI is going to be a bigger deal than people think, and also a smaller deal than people think, at the same time."},
    {"h": "wisdom_acct", "k": "aphorism", "t": "the work you avoid is usually the work that matters. the rest is just motion you can point at"},
    {"h": "shreyas", "k": "aphorism", "t": "strategy is choosing what not to do. most roadmaps are a list of things nobody was brave enough to cut"},
    {"h": "founder_zen", "k": "aphorism", "t": "speed is a feature until it is a habit. then it is technical debt with good PR"},
    {"h": "naval2", "k": "aphorism", "t": "specific knowledge is knowledge you cannot be trained for. if society can train you, it can replace you"},
    {"h": "quiet_builder", "k": "aphorism", "t": "consistency beats intensity, but only if you are consistent about the right thing"},

    # --- self-deprecating (punching-down risk) --------------------------
    {"h": "dan_abramov", "k": "selfdep", "t": "spent all day debugging. turns out it was a missing await. i have 12 years of experience"},
    {"h": "tired_dev", "k": "selfdep", "t": "shipped a migration that dropped a column on friday at 5pm. i know. i know."},
    {"h": "honest_founder", "k": "selfdep", "t": "we spent four months building a feature two customers asked for and zero customers used. my call, my mistake"},
    {"h": "junior_dev", "k": "selfdep", "t": "spent three hours on a bug. it was a typo in an env var name. i am not okay"},
    {"h": "burnt_out", "k": "selfdep", "t": "forgot to renew the domain. site was down for six hours. somehow nobody noticed, which hurts more"},
    {"h": "solo_dev", "k": "selfdep", "t": "my test suite has been passing for a month because i accidentally disabled it. found out today"},
    {"h": "ml_intern", "k": "selfdep", "t": "trained for two days on a shuffled label set. the loss looked beautiful. i have no idea how to explain this in standup"},
    {"h": "startup_cto", "k": "selfdep", "t": "we picked the wrong database in 2023 and i have been paying interest on that decision every sprint since"},

    # --- questions (answer opportunity) ---------------------------------
    {"h": "curious_dev", "k": "question", "t": "what is the actual argument for running models locally when the API is cheaper and faster for almost everything?"},
    {"h": "new_founder", "k": "question", "t": "how do you decide when to stop iterating on a prototype and commit to building the real thing?"},
    {"h": "hiring_lead", "k": "question", "t": "what is the best signal you have found in an engineering interview that is not a live coding round?"},
    {"h": "indie_hacker", "k": "question", "t": "for those doing $10k+ MRR solo: what broke first as you grew, support or infrastructure?"},
    {"h": "ai_pm", "k": "question", "t": "how are teams actually measuring whether their LLM feature is getting better? everything I try feels like vibes"},
    {"h": "student_dev", "k": "question", "t": "is it still worth learning the fundamentals deeply when the model writes most of the boilerplate anyway?"},
    {"h": "ops_person", "k": "question", "t": "what does your on-call rotation look like at under 15 engineers? we are burning people out"},
    {"h": "designer_q", "k": "question", "t": "does anyone have a good pattern for showing model uncertainty in a UI without scaring the user?"},

    # --- flexes / milestones (envy + generic-praise risk) ---------------
    {"h": "levelsio", "k": "flex", "t": "just crossed $200k MRR on a product i built alone in 6 weeks. stop overthinking and ship"},
    {"h": "bootstrapper", "k": "flex", "t": "18 months, no funding, 340 paying customers, profitable since month 7. slow is fine"},
    {"h": "ex_faang", "k": "flex", "t": "quit my job at a big tech company to build alone. six months in and i have never been more tired or more sure"},
    {"h": "app_dev", "k": "flex", "t": "our app hit 1M downloads today. the whole thing is still a single postgres instance and a rails monolith"},
    {"h": "agency_owner", "k": "flex", "t": "went from freelancing at $60/hr to a productized service at $8k/mo per client. same work, different packaging"},
    {"h": "youtuber_dev", "k": "flex", "t": "100k subscribers. four years. 380 videos. the first 300 got almost nothing and that was the point"},

    # --- complaints / frustration (empathy opportunity) -----------------
    {"h": "frustrated_dev", "k": "complaint", "t": "every AI coding tool is great for the first 200 lines and then confidently rewrites something that was already correct"},
    {"h": "ops_rage", "k": "complaint", "t": "third cloud provider outage this quarter and the status page was green the entire time"},
    {"h": "pm_pain", "k": "complaint", "t": "spent the whole week in meetings about a decision that three people could have made in twenty minutes"},
    {"h": "api_hater", "k": "complaint", "t": "the docs say the endpoint returns an array. it returns an object. the example returns null. all three are current"},
    {"h": "onboard_pain", "k": "complaint", "t": "signed up for a tool today and hit four modals, a survey and a calendar link before I saw the product"},
    {"h": "recruiter_rage", "k": "complaint", "t": "seven rounds for a mid-level role, then a take-home, then ghosted. the market is not tight, hiring is just broken"},
    {"h": "ml_ops", "k": "complaint", "t": "our model retrains nightly and nobody can tell me what changed between last week's version and today's"},

    # --- data / receipts (counter-example opportunity) ------------------
    {"h": "growth_data", "k": "receipt", "t": "we tested 40 landing page variants over 6 months. the winner was the one with fewer words and no illustration"},
    {"h": "churn_analyst", "k": "receipt", "t": "our churn was not a pricing problem. 70% of cancellations had not used the core feature once in 30 days"},
    {"h": "perf_eng", "k": "receipt", "t": "shaved 800ms off first paint and conversion moved 4%. the 800ms was almost entirely fonts and a analytics script"},
    {"h": "support_lead", "k": "receipt", "t": "half our support tickets were one confusing empty state. we rewrote 40 words and volume dropped by a third"},
    {"h": "sales_eng", "k": "receipt", "t": "deals we lost on price came back at the same price nine months later. deals we lost on trust never came back"},
    {"h": "ab_tester", "k": "receipt", "t": "removed the onboarding tour entirely. activation went up 9%. people wanted to click things, not read about clicking"},

    # --- meta / platform (self-referential AI risk) ---------------------
    {"h": "algo_watcher", "k": "meta", "t": "the reply section is the whole platform now. the timeline is just where you find something to reply to"},
    {"h": "creator_econ", "k": "meta", "t": "engagement bait works until your audience learns your name means bait. then nothing works"},
    {"h": "twitter_meta", "k": "meta", "t": "everyone posting AI-generated replies thinks nobody can tell. everyone can tell. the tell is that it agrees with you"},
    {"h": "bot_hunter", "k": "meta", "t": "you can spot the AI replies by the em dashes and the fact that they restate your post before adding nothing"},
    {"h": "growth_hacker", "k": "meta", "t": "reply guys who add real information grow. reply guys who add enthusiasm get muted. the algorithm learned this before we did"},
    {"h": "quiet_poster", "k": "meta", "t": "posting less and replying more was the single biggest change to my reach. took me three years to try it"},

    # --- money / business (opinion opportunity) -------------------------
    {"h": "vc_thoughtboi", "k": "money", "t": "founders: your seed round is not an achievement. it's a debt you took on to prove something. act accordingly"},
    {"h": "saas_metrics", "k": "money", "t": "if your CAC payback is over 18 months you do not have a growth problem, you have a pricing problem"},
    {"h": "angel_investor", "k": "money", "t": "the best companies I have backed all looked like bad ideas that one person understood unusually well"},
    {"h": "pricing_guy", "k": "money", "t": "raise your prices. the customers who leave were the ones filing the most tickets anyway"},
    {"h": "cfo_type", "k": "money", "t": "burn multiple is the only startup metric that has never lied to me"},
    {"h": "solopreneur", "k": "money", "t": "revenue is the only validation that survives contact with your own doubt at 3am"},

    # --- career / hiring (advice-lecture risk) --------------------------
    {"h": "career_coach", "k": "career", "t": "the fastest way to get promoted is to make your manager's hardest problem disappear without being asked"},
    {"h": "eng_lead", "k": "career", "t": "juniors who ask good questions in public channels grow twice as fast as the ones who DM me"},
    {"h": "job_seeker", "k": "career", "t": "applied to 140 roles, 6 replies, 2 onsites, 1 offer. posting the numbers because everyone hides them"},
    {"h": "switcher", "k": "career", "t": "left engineering for product and the hardest part was learning that being right slowly is worse than being useful now"},
    {"h": "staff_eng", "k": "career", "t": "the staff engineer job is mostly writing documents that stop three teams from building the same thing"},

    # --- product / design ----------------------------------------------
    {"h": "ux_lead", "k": "product", "t": "users do not read. they scan for the thing that looks like the button they wanted and click it"},
    {"h": "product_dev", "k": "product", "t": "we shipped a settings page with 40 toggles because we could not decide anything. that is not flexibility, it is cowardice"},
    {"h": "onboarding_pm", "k": "product", "t": "nobody finishes onboarding. they finish the first thing that gives them a result. design for that instead"},
    {"h": "mobile_dev", "k": "product", "t": "every feature you add makes the search worse for the feature people actually came for"},
    {"h": "ai_ux", "k": "product", "t": "chat is a terrible default interface for AI products. it makes the user do all the work of knowing what is possible"},

    # --- short / low-content (skip-gate test) ---------------------------
    {"h": "vague_poster", "k": "thin", "t": "big if true"},
    {"h": "morning_person", "k": "thin", "t": "gm"},
    {"h": "cryptic_founder", "k": "thin", "t": "soon."},
    {"h": "hype_short", "k": "thin", "t": "this changes everything"},
    {"h": "one_word", "k": "thin", "t": "shipped"},
    {"h": "engagement_bait", "k": "thin", "t": "reply with the one tool you could not work without and I will check out every single one"},
    {"h": "late_night", "k": "thin", "t": "it works. no idea why."},
]

assert len(CORPUS) == 100, f"corpus is {len(CORPUS)}, expected 100"

# How building software is changing at Anthropic

> A deepdive on what's changed in how the leading AI lab makes software. Ever more code review and testing is done by AI, two-pizza teams very much alive, and more. Details from inside of Anthropic
>
> Author: [Gergely Orosz](https://newsletter.pragmaticengineer.com/p/inside-anthropic)
> Published: Jul 28, 2026
> Source: [The Pragmatic Engineer](https://newsletter.pragmaticengineer.com/)

Much-improved AI tooling is changing how we build software, and I want to take a peek into how the future of software engineering may unfold under its influence. What better place for that than with tech’s most “AI-pilled” teams: the AI labs themselves.

So, I visited the two leading AI labs to see how teams and engineers do things day to day. In this article and in an upcoming follow-up, I’ll share what I learned about how AI is reshaping software engineering principles many of us are accustomed to – and what’s stayed mostly the same despite the AI wave.

In a later article, we’ll compare findings from Anthropic and OpenAI to see what their ways of working might mean for the overall direction of software engineering.


![Inside Anthropic's HQ](2026-07-28-inside-anthropic/anthropic-hq.png)
*Inside Anthropic's HQ (left). AI development milestones framed on the wall (right)*

Thanks to Anthropic for showing me inside their lab in San Francisco. I talked with four people:

Katelyn Lesse, Head of Engineering for Claude Platform, whose organization owns the infrastructure that Claude runs on

Jarred Sumner, creator of Bun, now at Anthropic on Bun and Claude Code

Thariq Shihipar, who works across Claude Code engineering and education

David Hershey, at Anthropic’s Applied AI organization in a role resembling a sales engineer, working with customers like Cursor, Cognition, and Perplexity

Thanks to them, I got a sense of where things are headed at the leading AI lab – and possibly for the wider industry.

Before we continue, The Pragmatic Engineer will be on summer break for the next week and a half. This means no Thursday article this week, and no articles next week. I appreciate your understanding and support!

Back to today’s deepdive, we cover:

Complex & long: Claude Managed Agents. One of the most complicated projects took the Claude Platform team six months to ship, and created a new primitive to use at the agent infra level. Infra projects still need re-architecting mid-way through and take time to get right.

Twelve-month project done in 11 days: Bun rewrite to Rust. Migrating a 500K+ line project to another language used to take a small team a year, making it impractical. With Fable and $165K of tokens, it recently took the creator of the project less than two weeks.

Changing engineering practices. Inside the AI lab with more than 3,500 employees, prototyping is more fluid, verification is more time-consuming than implementation, code review and testing are increasingly done by AI.

Team-level changes. Design is more ongoing and less upfront, teams work on more projects, a maximum of two engineers per project, and more.

Still the same: two-pizza teams, planning is important, PRDs are relevant in complex projects, context switching is a challenge, the ratio of time spent on coding vs testing not changing that much.

Changing the “standout” software engineer archetype? Deep understanding, including of a layer below what you work on, is valuable, along with the ability to coordinate work.

Will AI replace software engineering? The more hands-on software engineers get with AI at the lab, the less they fear their jobs are going away.

## 1. Complex & long: Claude Managed Agents

The Claude Platform team’s most complex project in the past year was building Claude Managed Agents, a pre-built harness for production agents that runs in the cloud on infrastructure managed by Anthropic, or on your team’s own infrastructure, with any sandbox you choose. The project took around six months from idea until launch in April. Katelyn Lesse, head of engineering for Claude Platform, shared the story.

![With Katelyn Lesse, at Anthropic](2026-07-28-inside-anthropic/katelyn-lesse.jpeg)
*With Katelyn Lesse, at Anthropic*

### Claude Platform

This team sits between the model/accelerator layer (Claude models operate on GPUs) and the product/application layer (with products like Claude Code and Claude Cowork):

![Where Claude Platform sits inside of Anthropic](2026-07-28-inside-anthropic/claude-platform-position.png)
*Where Claude Platform sits inside of Anthropic*

Katelyn on what the Platform team does:

“We’re on the ‘token hot path.’ The prompt comes in, then we tokenize it. Then, things like safeguards and billing all happen within our layer.”

What the Claude team calls “Platform,” I think more of as “API.” Claude Platform operates the API, and owns responsibilities an API would have. Of course, the team does more than that, and Claude Managed Agents is one case we cover here.

The platform layer is being migrated from Python to Rust. Originally, this layer was written for Python for the “usual” reasons at AI companies: it’s a convenient language and AI researchers use Python already, which enables quick iteration. But Python is single-threaded, and at scale, when the API is under high load, it’s not as performant as Rust.

### Harness infrastructure demand

The project came together due to customers wanting their own “harness infrastructure”, says Katelyn:

“We started with a model where you get an API to define an agent, then you get an API to start a session with an agent. The reality of what the world wants and needs right now is people running their own infrastructure. So, we started to build a self-hosted sandbox.

But then, what we started to hear from lots of customers is that they’re trying to hack harnesses together, running their own “harness infrastructure,” and this gave us the idea for Claude Managed Agents.”

### The largest part: planning

In this project, Katelyn said the single biggest matter was planning:

“There are products you can jump straight to prototyping, but then there are ones where you need to start by architecting it properly. For example, if we build a TypeScript CLI – which is pretty trivial for what needs to be built – we could go straight to prototyping. But with Claude Managed Agents, we needed to first figure out what we are doing.

Of course, we did some upfront prototyping for Managed Agents: hacking and spiking things. But prototyping itself was more about understanding the requirements.

Our planning process looked more like a typical pre-AI planning process. You know how every team has the project, where everyone comes up with some version of the same idea and people keep floating and circling it around until you finally do it? Managed Agents was this for our team. When we started the project, we had documents dating back up to two years about ideas and suggestions.

Post-planning, when the project officially kicked off, a PRD (product requirements document) was created:

“In the end, it was the Product Manager and the Tech Lead on our API Agents team who decided to pull the trigger and kick off this project. We’d get in a room, go through it, and get aligned. But it wasn’t just us: we’d have to align with teams around the business, other cloud providers, and other engineering teams. For example, we have a sandboxing team inside of the Platform org: and so this team was consulted on the design of Managed Agents, given this product would spawn a lot of sandboxes.

Just like before, we had a PRD, it was a Google Doc. We used a Google Doc because we needed to coordinate all interested people. This has not gone away.

Similarly, my product counterpart and I run product reviews.”

Some processes from before AI, like the PRD, are still useful in complex projects today, for getting large groups of people on the same page.

### Build for an internal customer first

With planning complete, the team decided to do a “spike” and stress-test the idea and architecture, by building the backend of Claude Code on the web. Remote execution of code with an agent harness was a similarly shaped problem to the one they wanted to solve for customers. The thinking was to start by solving it for the Claude Code team before tackling it in a more generic way for customers.

Internal teams are more fluid than before AI. Katelyn:

“Pre-AI, we might have hit the Claude Code team up with a bunch of big requirements documents, and they would have then hit us back with another set of documents. Now it was much easier: someone on our team built a few components, took it over to the Claude Code team, and they started to hack around it. We could figure out how this component plugs into this part of their product, and the other way around. It was just a faster and easier process, getting this first internal version of the product up and running.

Aligning with other teams on interfaces remains important, and it’s easier. Back in the day, you’d have to come with a fully spec’d interface to use. Now, we could do it a lot more fluidly: we could stand up a stub service that shadowed traffic to start with, and iron out the interfaces with the Claude Code team as we went. They did some hacking on it and gave feedback, we made changes while building out the service under the interface, then went back to make it work.”

They launched a service for Claude Code’s mobile app to spin up a sandbox, boot up Claude Code and run it. The service went to production and the Claude Platform team took the learnings.

### Re-architecting midway through

It’s likely a familiar scenario many engineers can relate to, that after planning a project and getting underway, you see that you’re going to need to change the architecture. It happened on this project, too.

The platform team ended up re-architecting Managed Agents based on learnings from the Claude Code “spike.” Re-architecting meant decoupling the “brain” of Claude and its harness from the “hands” (sandboxes & tools that perform actions) and the “session” (the log of events). Each became an interface that made few assumptions about each other.

![High-level architecture of Claude Managed Agents after the re-architecture](2026-07-28-inside-anthropic/managed-agents-architecture.png)
*High-level architecture of Claude Managed Agents after the re-architecture*

The team also built an abstraction around vaults and credentials. Credentials can safely be stored inside a vault. All calls using credentials are made via a proxy which has a session token. It is the proxy that fetches the right credentials from the vault: the credentials are never seen by the agent, sandbox, or session. Credentials are only injected at the egress boundary when the service is invoked:

![Adding credentials the harness never sees](2026-07-28-inside-anthropic/credentials-vault.png)
*Adding credentials the harness never sees*

Internal “dogfooding” helped surface hard problems to solve. A few examples:

Reliability and scalability: these are really hard to do well for agents because if connection to the sandbox is lost, the whole agent dies and you lose state

Credentials and access control: also hard and problematic, especially when first building the service

The Managed Agents team shared more about this re-architecting project.

The project took about six months, by no means a rapid process. Katelyn emphasized that pre-AI, a project like this would have probably been in the realm of two years. Managed Agents is one of the biggest projects the Claude Platform team has built, and more complex than it looks: for example, adding support for running agents on AWS, GCP and Azure.

## 2. Twelve-month project done in 11 days: Bun rewrite to Rust

As covered before, Jarred Sumner is the creator of Bun, a popular JavaScript runtime with 22 million monthly downloads currently and Claude Code as a dependency.

![With Jarred Sumner (left), creator of Bun](2026-07-28-inside-anthropic/jarred-sumner.jpeg)
*With Jarred Sumner (left), creator of Bun*

Bun is written in Zig, a performant, productive language. However, it’s not memory safe and memory issues kept coming up. Jarred thought that rewriting the project to an also-performant, memory-safe language like Rust could be an option – except that rewrites like this turned out as follies in the past. Jarred (emphasis mine:)

“Historically, rewrites are a terrible idea. Excluding comments, Bun is 535,496 lines of Zig. A rewrite in another language would take a small team of engineers a full year. It would mean freezing bugfixes, security fixes or feature development for that time. The least risky approach to getting something shippable would be a mechanical port from Zig to Rust, with the minimal number of behavioral changes, using the exact same test suite we already use for testing Bun.

Fortunately, Bun’s own test suite is written in TypeScript which means it doesn’t depend on the runtime’s programming language.

A year of zero user-facing impact was not an option we could consider. So, enforcement through code style to fix stability issues was our best bet, and was our plan when we added Rust-inspired smart pointers to Bun’s codebase.

But honestly, I didn’t want to do it. Homegrown smart pointers offer worse ergonomics than Rust, with none of the guarantees.”

But then, Jarred asked if AI could do the heavy lifting and wondered how much the migration could be sped up. In the end, he completed the rewrite from start to merge in 11 days, using 64 parallel agents and $165,000 in tokens at API price. Here’s Jarred on how his AI-heavy rewrite compared:

“By hand, I think this would’ve taken three engineers with full context on the codebase about a year, during which time we wouldn’t be able to improve Node.js compatibility, fix bugs, fix security issues or implement new features. We never would’ve done that. The realistic alternative was to do nothing and keep fixing the bugs at the top of this post forever.”

There was a lot more to the project than typing out the “...make zero mistakes” prompt:

Jarred made a detailed plan and style guide on how to migrate

He set up the project so agents would not use Git worktrees which he found slow, but worked on different files in the same codebase

He created an orchestration system where each AI agent came up with suggestions of what to change, but did not make a change to the file to avoid conflicts; an orchestrator AI agent created the commits

The most time and tokens went on fixing the compile bugs, tests, and verifying that things worked

Bun itself has a very robust test harness: when all tests pass, it’s a high-confidence signal that the rewrite works

Crucially, Jarred is the ultimate domain expert in Bun: he created the project and knows the codebase better than anyone

The rewrite has been shipped to production and powers Claude Code today.

We cover a lot more on this in What can we learn from Bun’s rapid Rust rewrite with AI?

## 3. Changing engineering practices

So, what has changed in how teams build software at Anthropic, compared to the pre-AI days? That’s the question of this article, and it seems that many things are different. Let’s go through it:

### AI lab-specific practices

Some things as normal as breathing at AI labs like Anthropic stand out as different with an outside perspective:

Everyone runs multiple AI agents all the time. Running 3-10 parallel agents is a given. Folks I talked with had their agents running in the background or cloud.

No token budget, usage not tracked. One major difference between AI labs and everyone else is that there really is no token limit or token leaderboards that promote tokenmaxxing; people already use agents all the time.

Very high autonomy. Work is becoming more structured inside AI labs, but there’s still massive autonomy compared to Big Tech and most startups. When everyone has unlimited tokens, it’s pretty easy to prototype any idea.

Prototyping and “spiking” is far more fluid

It was several times faster to prototype early approaches for Claude Managed Agents. Similarly, “spiking” the Claude Code mobile backend implementation was much faster than pre-AI, Katelyn told me.

### Verification takes longer than implementation

Jarred made a point about the split between implementation and validation in his 11-day rewrite to Rust. Roughly, it was:

![Implementation of the Rust rewrite took far less time than fixing it up, then validating that it works as expected](2026-07-28-inside-anthropic/implementation-vs-verification.png)
*Implementation of the Rust rewrite took far less time than fixing it up, then validating that it works as expected*

The “implementation” part of rewriting the code from Zig to Rust took about 15% of the time, while 85% went on fixing things up: getting it to compile, fixing tests, verifying that it worked.

### Most tokens no longer spent on implementation

Thariq:

“We see that few tokens are spent on actual implementation. Most are spent on discovery of unknowns, prototyping, mocking, and then in verification and testing.”

Jarred’s Bun rewrite echoes this: he spent more tokens on fixing up the implementation and verifying that it worked than on the implementation itself!

### Code review and more testing by AI

Jarred:

“Critiquing the code and testing it with agents is a new approach we do a lot more of. I think a lot about trust when you merge a lot of code. How do you merge 100+ PRs a day, and make sure the code works? At this pace, you need to trust the code without the ability to read it all yourself. And I think it’s a few things:

Code review: it needs to be really good and automated. I’m clearly tooting our own horn here, but I find Claude’s code review to be really good. Claude’s code review catches bugs that would take me an hour of closely reading the code to figure out. The caveat is that it’s expensive!

Security scanning: for this Rust rewrite we did 11 runs of the Claude Security Scanner.

Fuzz testing: we’ve also been doing different types of fuzzing (fuzz testing), where we had Claude write a fuzzer for things like parser fuzzing.

Running out-of-process testing, where it happens in a different process/session from coding, is one way to build trust in the code. I expect more of this.”

### New pattern: fanning out work to AI

Jarred described a new way he works:

“A new approach I’m using is fanning out a lot of the work to many Claudes at the same time. I did this with the Bun rewrite, but I use it for other work. This approach works very well for me, and I feel it’s pretty underused.”

### Time-saving automations powered by agents more widespread

Jarred listed several time-saving automations set up by the Bun team to run an active open-source project with a small team, while the team works on Claude Code:

Every time someone files an issue, Claude runs to try and reproduce the issue. If it succeeds, it starts another container, which then tries to fix the issue and submit a PR.

The agent tasked with submitting a PR has to write a test that fails in the system version (the one without the patch) of Bun, and passes in the debug build with the patch, before it is allowed to submit a PR

There are other automations, like if there is no test, the PR is auto-rejected; all linters are run: Claude Code review is run, CodeRabbit’s code review is run, and the agents go back and forth on the GitHub pull request

### Auto-merge of pull requests: coming soon?

Pull requests are merged manually when all quality gates pass, but this could become automatic at some point. Once all the above checks pass, all (AI) code review comments are addressed, tests are added to new code, etc. As an interesting aside, a lot of GitHub activity is Claude talking to Claude!

![Claude talking to Claude](2026-07-28-inside-anthropic/claude-talking-to-claude.png)
*Claude talking to Claude. Source: Bun GitHub*

Claude talking to Claude. Source: Bun

But manual merging may vanish in low-risk cases, at least for the Bun project. Jarred told me:

“Today, a person presses ‘merge’ but within a few months, I expect:

Automated reviewer LGTMs

→ another Claude with a fresh context window judges if it’s simple and low blast-radius

→ if it is: auto-merge!”

### Test assumptions with each model generation

Inside Anthropic, the team keeps testing their priors. Thariq gave an interesting example:

“The thing with agents is that you have to revisit any assumptions you have made because it can change with a new model generation. For that reason, we deleted 80% of the Claude Code system prompt recently because the model has gotten smarter.

Using HTML is another assumption we needed to re-examine. HTML is one of those things which Claude is a lot smarter at than many of us expected. I’ve started preferring HTML as an output format over Markdown, and see this being used by others on the Claude Code team.

HTML can convey much richer information compared to markdown, HTML documents are easier to read and share.”

## 4. Team-level changes

At Anthropic, there are also changes in how engineering teams operate, compared to pre-AI.

Design is less upfront & more continuous on product teams

Katelyn:

“As an engineer, you used to be able to say, “here’s a perfect, beautiful design.” In some teams inside the Anthropic org, upfront planning is gone. There are parts of the Anthropic org where people have said things like “we don’t write PRDs” or “we don’t write technical design documents anymore.” Those teams go straight to prototypes.”

It’s worth bearing in mind the differences between platform and product teams, and the maturity of products. The more platform-like and mature a product is, the more that the value of upfront planning rises.

Silos no longer a worry

Katelyn confirmed that while the typical size of the platform teams has not changed much – they’re still 6-8 people – but now, they take on far more projects than in the past.

Pre-AI, if a team worked on more than one project at a time, members would complain about feeling siloed: cut off from what peers on the team were doing. But now, it’s common to find 3-8 parallel projects on a 6–8-person team.

Two engineers max on individual projects

Katelyn:

“On an individual project, you often cannot have more than two people working on it.

This is because each engineer is already running several agents. And so as an engineer, you’re already fighting against your agents, which are stepping on each other’s toes on implementation. And in this setup, you just cannot have that many humans, who also come with all their agents! This is especially true when the human is doing more of the actual design of the system.”

Katelyn has a point: before AI, it was also a recipe for disaster to have several tech leads on the same project!

Internal teams iterate faster

Pre-AI, teams went through the back-and-forth of iterating on an implementation using design documents. Now, for the Claude Managed Agents project, it took the form of the Claude Code team hacking around the implementation. Katelyn told me the whole process felt faster and easier than before AI tools.

## 5. Still the same

Here’s what I gathered from my four conversations with Anthropic insiders about what’s not changed in software engineering much since AI came along.

Two-pizza teams

On the Platform side, there are 6–8-person teams as there were before AI in platform organizations. Katelyn on why this hasn’t changed:

“I still have teams whose job it is to own a piece of software, iterate on it, own oncall, and so on. While each of these humans are supercharged by AI, the size and shape of the team is still similar. We still have two-pizza teams.

Everybody on the team needs to have a deep understanding of the system. They need to understand where it’s going, then orchestrate their Claudes to build in that direction. But people still need to internalize how their system works. So, the system they work on cannot become so big that someone doesn’t understand it.

But then, you also need enough people so that when someone is oncall, another is on vacation, and someone is sick, you still have redundancy and the team can continue to make progress.

One thing I’ve heard from some people is “we have two humans and a bunch of agents.” I reply that this isn’t where we’re at: we still have teams with 6-8 people on average.”

Planning still important

Both Katelyn and Jarred mentioned the importance of planning, but with different focuses:

For Managed Agents, the planning process was the most similar to how it was pre-AI, due to the complexity:

Infrastructure complexity: the platform itself is complex, with lots of parts that needed consideration

The number of people/teams involved: a lot of people and groups needed to be aligned: not just the Platform team, but other teams at Anthropic, and working with three different cloud providers.

This takes time to get it right!

For the Bun rewrite, Jarred started by spending three hours talking to Claude about how to map patterns from their Zig codebase closely to Rust

For complex projects with many people or systems, planning still matters at Anthropic. Even for kicking off a “simpler” project like a migration, a few hours of intense preparation and planning is seen as worthwhile.

Also, let’s not forget that in the Bun rewrite, the planning part was greatly shortened by Jarred being the creator and de facto domain expert. Also, there were no other engineers, which further shortened the process.

### PRDs in some teams

PRDs are for when lots of people need to be coordinated, and the Claude Managed Agents project is a good case. PRDs inside Anthropic are Google Docs because the point of this document is for it to be debated, and for agreement reached about a complex project’s high-level goals and design approach.

### Platform/product split & prototype/mature product split

There’s a big difference between building a product and building a system, as with upfront design being far more of a thing with systems than it ever is with products.

For products, there is maturity to consider. For example, Claude Code during infancy was more of a prototype. It then found product-market fit, and today it’s a mature product with millions of customers. Prototyping can be a great way to get a product off the ground. But the more mature it becomes, the more planning might be needed for things like a new feature that needs to integrate nicely with other parts of the product, or product-wide changes.

It was the same pre-AI; we covered how Uber introduced platform and product teams in 2014 in The platform/program split at Uber, the first-ever Pragmatic Engineer article.

### Platform work challenging as ever

Katelyn, again:

“There’s a bit of a different working culture between application development and platform development. For example, when we’re building new things into the platform, we deploy on all three clouds (AWS, GCP, Azure), and deploy in several regions. We’ll eventually start deploying internationally. It makes for a lot of complexity.

We have specialized teams within the org and a specialist team in each layer. We have abstraction layers in place, so most people don’t have to think about the physical infrastructure. But even so, within my org, I have a team who understand what queue implementations on each of the different clouds look like. In some cases, we’re running bare metal, and in other cases we’re running managed services. We always have a team that understands every part of a layer, and then other teams don’t need to become so specialist in a given layer.”

### Context switching still hard

I asked if it’s now easier to ask an engineer on another team for help with your own work. I figured it should be when everyone uses AI, as it makes getting back in “the zone” easy after returning to your work from lending a hand. Katelyn didn’t see it like that:

“Context switching, on one end, is easier, but it’s still very hard. In the past, it was a pretty big ask to go to an engineer doing deep work, to ask them to stop something to help you with feedback, or do some of your work. With AI, context switching is easier, but deep work has not gone away.”

### Agreement on interfaces still matters in cross-team engineering work

Reflecting on Claude Managed Agents, Katelyn told me it’s important to define the interfaces between the Platform team building Managed Agents and the Claude Code team using it, as per pre-AI. The difference is that it’s a bit easier to iterate with AI:

“Back in the day, you’d have to come with a fully spec’d interface you wanted to use with the team you’re integrating with (for us, Claude Code). Now, we can do it a lot more fluidly: we could stand up a stub service that shadowed traffic to start with, and iron out the interfaces with the Claude Code team as we went. They did some hacking on it, gave feedback, we made changes to it – we were building out the service under the interface – to make it work.”

Coding/testing time split hasn’t changed

Time spent coding vs on testing hasn’t changed all that much from before AI, according to Jarred:

“The AI writes pretty much all the code, but we have the AI write pretty much all the tests as well. Before AI, for production-ready software, we spent about the same time writing tests as we did on writing code. This is still the case with AI. You need to have a way to trust your code, and tests are probably the best way to.”

What happens to the time created by not spending it on writing code and tests? Jarred says he doesn’t have more free time these days:

“I now spend more time on making sure everything works and on doing a lot more stuff than before. There’s so much stuff in Bun that we would not have shipped [without time savings from AI]. For example, we have a Markdown parser and a YAML parser on Bun. I used to have a list of everything I’d like to do in Bun, and it’s pretty much all there!

The bottleneck used to be me or someone else spending a bunch of time writing code, then spending just as much time figuring out how to test it all and what test suite to build. But now, we can just mention Claude in Slack (using Claude Tag), it runs and gives us a PR to start with.”

### Learn something new to make something great

Thariq Shihipar is responsible for much of the educational content on Claude Code. He’s a software engineer who tinkers a lot and shares what he learned; for example, how he got Fable to edit a launch video. He also works with the Claude Code team and engineers outside Anthropic.

One thing Thariq doesn’t see changing in engineering is that it takes special effort to make something truly great. As he told me:

“When you’re looking at how to make something great, you usually need to learn something new. Say that you want to make a video game. People love vibe coding video games, but there’s so much to learn to make a really good game!

For example, if you’re making a flying game controlling a plane, there’s so much depth to how the plane reacts to the left and right movement. If you know about the domain, then Claude can work with you on it. But in my observation, you need to expand your own knowledge to be able to work efficiently with it to get to an end result that feels “great.”

## 6. Changing the “standout” software engineer archetype?

I asked both Katelyn and Jarred if and how the “standout” software engineer archetype has altered with the adoption of AI tools, and which traits make for a solid engineer, in their view.

### Understand, understand, understand

Jarred:

“It’s still really important to understand how everything works, end to end. Also, it’s important to not trust that because something was assumed to be true, that it still is true.

A lot of programming is still like poking around and seeing what happens. So, have the mental model in your head and stay in charge. As a person, I am still deciding what to merge, and what I should work on. I’m still very nitpicky about exactly the way it should be done, and this comes from understanding. I think you can also just use AI to help you understand faster.”

Katelyn said similar:

“Understanding is table stakes for solid engineers. Make sure you understand not just what the LLM does, but also a layer underneath it.

The problem with models is the context window is finite. Our research team is working extremely hard so the model can feel like it has almost infinite context and that it will make the right decisions and store them away in memory, then pull it back in, and keep the context window as clean as it can. But, at the end of the day, the model’s context window is finite and nowhere close to what a human brain can store – so keep investing in developing your own mind while you work with agents. Understanding and learning with the model is a great way.”

Katelyn stressed that as an engineer, it’s important to understand not just the current layer, but also the one below it. For example, if building a product that uses queues, understand the queue primitive or implementation you’re using.

### Coordination skill also table stakes

Katelyn:

“Coordination and alignment remain very important skills for engineers. Even if it gets easier to coordinate groups of people with AI tools, it’s not going away!”

I will add my own observation: every engineer I’ve met at Anthropic was a good communicator and articulate in expressing their ideas. I suspect the company would not hire folks who lack fluency in this and debating ideas.

### Engineers designing software

Katelyn:

“Engineers are the ones doing the design, and it will probably stay like this for some time. Even as the models get better at technical design and systems design, I cannot see the model replacing my engineers on large-scale distributed systems design.”

Steering the model in the right direction is very important. One more reason for understanding what the model does – and the layer below it – is that the model will get things wrong, inevitably. When it does, you want to steer the model to get it right.”

Being “in the zone” has changed

Jarred was a standout programmer pre-AI, and has spent a lot of his time “locked in” on writing code. Now that AI writes most of his code, I asked if he still gets “in the zone.” He told me:

“Being in the zone” as a developer is definitely different now. I still do things in serial order, sometimes. Not writing the code, but when you’re doing one project, there’s a lot going on and you see it coming together, step by step. As long as the feedback loops are quick enough, I find myself in a kind of “zone.” It’s admittedly different from the “coding” zone, but it’s really fun.

Another thing I like is that I can be away from my computer, and things are still happening. For example, I can be on a run and just check how the agent running in the background is doing.

## 7. Will AI replace software engineering?

In February 2025, Anthropic CEO Dario Amodei made an eye-catching prediction, saying: “coding is going away first, then all of software engineering”. His comment:

“I think coding is going away first, done by the AI models first. And the broader task of software engineering will take longer. Doing that end-to-end [AI replacing software engineering] is going to happen as well.

But the elements of design, or making something that is useful to the user, or managing teams of AI models: those things may still be present. Even if you’re doing 5% of a task, that 5% gets super amplified”

I asked Katelyn, Jarred, and David Hershey for their takes: do they see software engineering “going away” and being “solved” by Claude? Interestingly, people who build software day-to-day are not worried about models taking over software engineering. Katelyn and Jarred are confident they have lots of work to do, and feel busier with software engineering than before!

They do lots of planning, coordination, verification, coming up with more effective ways to manage agents, and building novel software.

David Hershey, who focuses heavily on customers, reckons the models will eventually take over software engineering:

“I have a very hard time believing that the models will eventually not take over this thing that we call software engineering. It’s going to get better than us at nearly all of it.

The model can already listen to customer feedback, and write the software to solve problems customers have. It’s hard to point to something it cannot do.

I watched models become better software engineers than me, and I have a software engineering degree. I don’t claim to be a great software engineer, but I don’t see why it would stop at my level and not keep outdoing most software engineers.”

Based on my small sample size, it seems that the more hands-on someone is in software engineering, the less they believe the models will take their jobs. Both Katelyn and Jarred stressed the importance of understanding everything about your system, how it works, and to keep going ever deeper in understanding it – especially with the help of AI!

### Takeaways

It was an interesting day at Anthropic, with much food for thought afterwards about the ways that software engineering has changed and where it might be headed next. Thanks very much to everyone there for welcoming me and sharing their time.

I suspect the way software engineering is done inside Anthropic will be how many “AI-native” startups will operate soon – if not already. Specifically:

Projects done by a maximum of two engineers, and a bunch of AI agents

Design is more ongoing and less upfront

A lot more prototyping, with more detailed planning only for complex projects

… but things still take time, even with faster coding! AI has not magically solved how to build quality software that’s complex and does something customers want.

The software engineering bar has shifted upward at Anthropic. Every engineer I talked with there is “standout” in more than one dimension:

Solid engineers pre-AI: these folks were very good engineers before the AI wave

Push themselves every day: they experiment with new approaches with (or without!) AI, change workflows, and keep learning how to best employ the latest models in their work

Collaboration and coordination are key: they self-manage themselves, stakeholders, and teams when needed

High-profile labs in leading positions like Anthropic get to hire the “best of the best” software engineers, and one question is what this means for companies without the brand recognition and funding of an Anthropic. Perhaps this kind of setup only works when you can hire such standout engineers, and for companies without the ability to attract such standout folks, attempting to copy what Anthropic does could well result in disappointment, without similarly motivated and capable staff.

Today, Anthropic generates five times more revenue per employee than Big Tech. Anthropic is made up of somewhat over 3,500 people, and annual revenue run-rate crossed $47 billion this May. That’s roughly $13.5M in revenue per employee: at Meta it’s $2.7M/employee, Apple $2.6M, and at Google $2.2M. NVIDIA is the only major company that comes close with $6M/employee.

Revenue per employee is one dimension that validates Anthropic’s approach of using AI as much as possible in everything they do, including software engineering. Such revenue also allows them to keep hiring top talent with the biggest comp packages on the market.

We should state the obvious, that Anthropic is in the business of selling AI models, so using AI heavily is obvious for them. But they also support a very large number of customers and enterprises with a surprisingly small team, and using AI more than most companies is clearly one way to operate with so many fewer employees.

Teams are remarkably unchanged, though. One familiar part of how Anthropic works is that a “team” is still a core building block of the engineering organization, and it’s made up of 6-8 engineers as it was before AI.

The replacement of the team with two people and dozens of agents is not happening at Anthropic because it would not promote sustainable operations. As Katelyn said about the team size:

“One thing I’ve heard from some people is ‘we have two humans and a bunch of agents.’ I reply that this isn’t where we’re at: we still have teams with 6-8 people on average.”

I hope you found this look into how Anthropic works interesting. In a future article, I’ll share details from inside OpenAI following a visit to their offices, and we’ll have the chance to compare the two.
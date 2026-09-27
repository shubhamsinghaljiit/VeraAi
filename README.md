# magicpin AI Challenge Submission - Antigravity Bot

## Approach

Our goal is to build an intelligent, fast, and compliant merchant AI assistant that excels in the magicpin ecosystem. We use a deterministic framework for state management and rely on Frontier LLMs for generating compelling messages based on high-context inputs.

1. **Idempotent State Management**: 
   The server endpoints (`/v1/context`) safely store `category`, `merchant`, `customer`, and `trigger` states in memory using versioning. It guarantees that we always utilize the most recent payload correctly.
2. **Deterministic Context Construction**:
   When `/v1/tick` is called, the bot unwraps nested triggers and fetches related local merchant and category objects, ensuring no necessary context is missing before pushing it down to the LLM.
3. **Structured Response Generation**:
   We employ a highly constrained prompt ensuring the model adheres to:
   - **Specificity**: Enforced strict inclusion of exact metrics and verifiable benchmarks.
   - **Compulsion**: Engineered to use FOMO (loss aversion), curiosity, and social proof.
   - **Constraints**: 100% JSON-structured outputs mapping accurately to the test harness format, avoiding hallucinated data, and restricted to a single binary YES/NO CTA.
4. **Resilient Conversational Fallbacks**:
   The `/v1/reply` endpoint operates intelligently to safely transition intent, aborting (returning `{"action": "end"}`) immediately when faced with automated/hostile responses, or advancing workflows precisely when explicit affirmative consent is detected.

## Model Choice

We utilize **Gemini 1.5 Pro** as our core reasoning engine (`bot.py` leverages `google-generativeai`).

*Why Gemini 1.5 Pro?*
- Superb adherence to strict system instructions (e.g. constraints not to fabricate data, structured JSON compliance).
- Speed is excellent which ensures we effortlessly beat the 30-second timeout constraints across large batch ticks.
- Multilingual and Code-Mixing capabilities make it a champion at natural "hinglish" combinations necessary for real-world merchant demographics on WhatsApp.

## Tradeoffs

1. **Synchronous vs. Asynchronous generation**: Currently, `bot.py` resolves ticks synchronously in a loop. For the constraint of `10 requests/sec` and `20 actions per tick`, this adds latency to large batches. To scale effectively for thousands of merchants, asynchronous queues (e.g., Celery or asyncio processing) would be adopted.
2. **LLM Generation Latency**: There's an innate delay caused by prompting an LLM for each unique message. Although we have heuristic fallbacks to ensure <30s execution for failing APIs, caching similar responses across exact-matching merchant states and triggers could further optimize speed.
3. **In-Memory Store**: We used a simple global dictionary `db` for context to prioritize speed and demonstration. In a production scenario, this needs to be a durable store like Redis to withstand application restarts.

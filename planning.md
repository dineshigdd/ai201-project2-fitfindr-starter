# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Search the mock listings dataset in `litings.json` for items matching the description,  optional size, and optional price ceiling.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): descriptors indicating the style, current condition, features, and textual references to the physical sizing of the secondhand piece
- `size` (str): Specific size string value (case-insensitive) mapping to industry standards or platform-specific hybrid descriptors, such as "M", "US 8.5", or "XL (oversized)
- `max_price` (float): Maximum price (inclusive) of the piece, or None to skip price filtering.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
Returns a list of matching dicts with the followin feilds:
- id
- title
- description 
- category
- style_tags (list) 
- size
- condition 
- price (float) 
- colors (list) 
- brand
- platform
        
The list is sorted by relevance (best match first).

If there is no mactching items:
- Returns an empty list.
- But, does NOT raise an exception.

**What happens if it fails or returns nothing:**
If the tool returns an empty list:
- The planning loop (`run_agent`) in `agent.py` must catch this.
- It must immediately halt the sequential workflow (do not call subsequent tools like `suggest_outfit`). 
- It must update the session state with an error message and inform the user to revise their search parameters (such as changing keywords, sizes, or price ceilings).
 
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
suggest 1–2 complete outfit combination based on a given thrifted item and the user's current wardrobe.


**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A listing dict (the item the user is considering buying).
- `wardrobe` (dict): A wardrobe dict with an 'items' key containing a list of wardrobe item dicts.This paramter may be empty ,and should not raise any error.

**What it returns:**
<!-- Describe the return value -->
Returns a non-empty string with outfit suggestions. 
If the  wardrobe['items'] is empty:
- Offer general styling advice for the item.
- DO NOT raise an exception or returns an empty string.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If the wardrobe['items'] is empty:
- The tool will not return nothing; it returns a string containing general styling advice. The agent should handle this as a successful path, 
store the advice in `session["outfit_suggestion"]`, and proceed normally to call `create_fit_card`.

If no outfit can be suggested or the LLM encounters an error:
- The tool will return a descriptive error string. The agent must catch this, immediately halt the sequential workflow (do not call `create_fit_card`), 
set `session["error"]` to a helpful error message, and return the session early to inform the user.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Generate a short, shareable description (more like a caption to tha can share in Instagram/TikTok) of a complete outfit for the thrifted find.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str):  The outfit suggestion string from suggest_outfit() function
- `new_item` (dict): The listing dict for the thrifted item.

**What it returns:**
<!-- Describe the return value -->
Returns a string containing a short, creative, and shareable social media caption based on the outfit suggestion and item details.
If the incoming `outfit` string is empty or whitespace-only, tool returns a descriptive error message string,and DO NOT raise an exception.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If outfit is empty or an error message string is returned by the tool:
- The planning loop(`run_agent`) in `agent.py` must catch this failure.
- It will update the current session state by recording the problem in `session["error"]`.
- It halts the sequential workflow and returns the completed session early so the user interface can display the error.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
IF session["parsed"] is empty (failed to extract parameters):
     Create a helpful error message, store in `session["error"]`, and return the session early.
ELSE:
     Call `search_listings()` with the parameters in `session["parsed"]` and store the results in `session["search_results"]`.
 
     IF `session["search_results"]` is empty (no matching items found):
          Set `session["error"]` to a helpful message and return the session early. Do NOT proceed to downstream tools.
     ELSE: 
          Select the top result from `session["search_results"]` and store it in `session["selected_item"]`.
          Call `suggest_outfit()` tool in tools.py passing `session["selected_item"]` and `wardrobe`.
          Store the returned string in `session["outfit_suggestion"]`.

IF `suggest_outfit()` encounters an LLM error:
     Halt the sequential workflow, do not call `create_fit_card()`, set `session["error"]` to a helpful message, and return the session early.
ELSE:
     Call `create_fit_card()` passing `session["outfit_suggestion"]` and `session["selected_item"]`.
     IF `create_fit_card()` encounters an error or receives empty inputs:
          Set `session["error"]` to a helpful message and return the session early.
     ELSE:
          Store the returned caption string in `session["fit_card"]`.
          Return the completed session dictionary successfully.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
- The raw user input query is processed and its extracted parameters(description, size, max_price.) are stored in `session["parsed"]`.
- If an issue occurs at any step in the pipeline, the error description is stored in `session["error"]`.

- `session["parsed"]` is passed into the `search_listings()` tool.
- The returned list of matching items from `search_listings()` is stored in `session["search_results"]`.
- The top result from `session["search_results"]` is extracted and stored in `session["selected_item"]`.

- Both `session["selected_item"]` and the `wardrobe` dictionary are passed into the `suggest_outfit()` tool.
- A valid text response returned by `suggest_outfit()` is stored in `session["outfit_suggestion"]`. 
- Any invalid values or API network exceptions are caught and stored in `session["error"]`.

- `session["outfit_suggestion"]` and `session["selected_item"]` are passed into the `create_fit_card()` tool.
- A successful caption string returned by `create_fit_card()` is stored in `session["fit_card"]`.
- If `create_fit_card()` fails or receives empty inputs, the resulting error string is stored in `session["error"]`.

---

## Error Handling
For each tool, describe the specific failure mode you're handling and what the agent does in response.  

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| **`search_listings`** | No results match the query | Instead of calling `suggest_outfit`, update the session state with an error message in `session["error"]` and halt the workflow early. |
| **`suggest_outfit`** | Wardrobe is empty | Save the fallback general styling advice string to `session["outfit_suggestion"]` and proceed normally to the next step (`create_fit_card`). |
| **`suggest_outfit`** | No outfit can be suggested or the LLM encounters an error | Halt the sequential workflow (do not call `create_fit_card`), set `session["error"]` to a helpful error message, and return the session early. |
| **`create_fit_card`** | Outfit input is missing, empty, or whitespace-only | Set `session["error"]` to a helpful error message and return the session early. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->
```
User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► [ERROR] "No listings found..." ───────►┤
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │ LLM Failure / Exception                    │
    │       ├──► [ERROR] "LLM failed..." ───────────────►┤
    │       │                                            │
    │       │ Success: returns text string               │
    │       ▼                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │ Incomplete / Empty Input                   │
            ├──► [ERROR] "Invalid outfit data..." ──────►┤
            │                                            │
            │ Success: returns caption                   │
            ▼                                            │
        Session: fit_card = "..."                        │
            │                                            └─ error path returns here
            ▼
        Return session

```

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
- Tool 1 implementation:
     - **AI Tool:** Claude
     - **Inputs Provided:** The `Tool 1 (search_listings)` specification block from this `planning.md` (inputs, return values, and failure modes) along with `Tool 1` starter code and  `TODO` comments from `tools.py`.
     - **Expected Output:** An isolated Python implementation of `search_listings()` that utilizes `load_listings()` from the data loader.
     - **Verification Strategy:** Before execution, I will review the code to ensure it filters by `description`, `size`, and `max_price` simultaneously and verify the implementation by writing automated test cases in `test_search_tools.py` to validate three distinct scenarios: a successful match, an edge case with optional `None` fields, and an impossible search to ensure it returns an empty list `[]` instead of raising an exception.
     1. A happy-path query matching specific listings (e.g., searching for a medium shirt under $50).
     2. A broad query with optional parameters set to `None` to ensure the filters are skipped gracefully.
     3. An impossible query (e.g., a designer gown for $5) to verify that it handles the failure mode cleanly by returning an empty list `[]` instead of throwing an exception.

- Tool 2 implementation:
     - **AI Tool:** Claude
     - **Inputs Provided:** The `Tool 2 (suggest_outfit)` specification block from this `planning.md` (inputs, return values, and failure modes) along with  `Tool 2` starter code and `TODO` comments from `tools.py`.
     - **Expected Output:** An isolated Python implementation of `suggest_outfit(new_item, wardrobe)` that correctly interfaces with Groq's `llama-3.3-70b-versatile` model.
     - **Verification Strategy:** I will review the code generated and verify the implementation by writing automated test cases in `tests/test_suggest_outfit_tools.py` to validate three distinct scenarios:
     1. **Successful Generation:** Pass a valid selected item and a populated example wardrobe to ensure the tool successfully calls the LLM and returns a valid text string containing outfit recommendations.
     2. **Empty Wardrobe Fallback:** Pass an empty wardrobe dictionary (`get_empty_wardrobe()`) to verify the code does not crash and gracefully falls back to returning a string with general styling advice.
     3. **LLM/API Failure Mode:** Simulating an invalid API environment or network exception to verify that the tool cleanly handles the error, sets a helpful message, and gracefully prevents a system crash.

- Tool 3 implementation:
     - **AI Tool:** Claude
     - **Inputs Provided:** The `Tool 3 (create_fit_card)` specification block from this `planning.md` (inputs, return values, and failure modes) along with the empty starter function and `TODO` comments from `tools.py`.
     - **Expected Output:** An isolated Python implementation of `create_fit_card(outfit: str, new_item: dict)` that correctly interfaces with Groq's `llama-3.3-70b-versatile` model 
                         with an elevated temperature (e.g., 0.7 or 0.8) to ensure unique caption variations.
     - **Verification Strategy:** I will review the code generated and verify the implementation by writing automated test cases in `test_create_fit_card_tool.py` to validate three distinct scenarios:
     1. **Successful Generation:** Pass a valid outfit suggestion and a populated listing item dictionary to ensure the tool successfully calls the LLM and returns a short shareable caption string.
     2. **Empty/White-space Outfit Fallback:** Pass an empty string `""` and a whitespace-only string `"   "` as the outfit input to verify the function bypasses the LLM completely , does not crash , and return a descriptive error message string.
     3. **LLM/API Failure Mode:** Simulating an invalid API environment or network exception to verify that the tool cleanly handles the error, sets a helpful message, and gracefully prevents a system crash.


**Milestone 4 — Planning loop and state management:**

- **AI Tool:** Claude
- **Inputs Provided:** The ASCII architecture diagram, along with the `## Planning Loop` and `## State Management` specification blocks from this `planning.md` file, alongside the starter code, execution comments, and `TODO` blocks of `run_agent()` fucntion in `agent.py` 
- **Expected Output:** Python implementation of `run_agent(query: str, wardrobe: dict)` that will act as the controller that interact witl tools and LLM.                        
- **Verification Strategy:** I will review the generated code to ensure it implements strict conditional routing, and verify it by executing execution checks in `agent.py` to validate three distinct architectural scenarios:
1. **Successful State Pipeline Flow:** 
     - Verify that the agent executes `search_listings`, stores the full results array in `session["search_results"]`, and assigns the top match to `session["selected_item"]`.
     - Verify that the agent safely passes `session["selected_item"]` into `suggest_outfit` and captures the generated text in `session["outfit_suggestion"]`.
     - Verify that the agent supplies both the suggestion and the item to `create_fit_card`, saving the final social media text to `session["fit_card"]`.
2. **Empty Search Branching (Early Return):** Test using an impossible query to confirm that when `search_listings` returns an empty list `[]`, the agent immediately logs a helpful feedback message into `session["error"]` and short-circuits the loop entirely—never invoking downstream tools on missing data.
3. **LLM/API Failure Mode:** Simulating an invalid API environment or network exception to verify that the agent cleanly handles the error, sets a helpful message, and gracefully prevents a system crash by handling early error returns.

  
**Milestone 6 - Connect to the UI Handler**
- **AI Tool:** Claude
- **Inputs Provided:** The starter code, execution comments, and `TODO` blocks of `handle_query()` in `app.py`.
- **Expected Output:** Python implementation of `handle_query(user_query: str, wardrobe_choice: str)` that will interact with the Gradio user interface.                        
- **Verification Strategy:**  I will review the generated code and run `app.py` to launch the Gradio interface. I will test it with a valid query to verify that all three visual output panels populate correctly on the webpage without errors.


---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
The agent will extract `description="vintage graphic tee"`, `size=None`, and `max_price=30.0` from the user query and store the result in `session["parsed"]`.
After that, the agent will call tool1 (`search_listings`) passing `session["parsed"]`.
The tool1 searches `listings.json` and returns a list of matching items. 
The agent saves the full list to `session["search_results"]` and assigns the top match (e.g., "Faded Band Tee — $22, Depop") to `session["selected_item"]`.

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
The agent call tool2 (`suggest_outfit`) passing `session["selected_item"]` and the user's wardrobe dictionary.
The tool2 prompts the Groq LLM to generate styling advice combining the new shirt with the user's wardrobe items (like their baggy jeans and chunky sneakers).
The returned values from `suggest_outfit` will be stored in `session["outfit_suggestion"]`


**Step 3:**
<!-- Continue until the full interaction is complete -->
The agent takes `session["outfit_suggestion"]` and `session["selected_item"]` and passes them into tool3 (`create_fit_card`). 
The tool3 prompts the Groq LLM to generate a creative, short social media caption, which is saved to `session["fit_card"]`.

**Final output to user:**
<!-- What does the user actually see at the end? -->
The agent returns the completed session dictionary, and the user sees the found item, the outfit styling tips, and the generated social media caption displayed cleanly on the screen.
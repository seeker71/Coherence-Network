# Use Coherence Network from ChatGPT

Create a Custom GPT that can create ideas, track work, measure impact, and navigate the full idea-to-realization lifecycle — all from ChatGPT.

## Option 1: Custom GPT with Actions (Recommended)

### Step 1: Create a Custom GPT

Go to [chat.openai.com](https://chat.openai.com) → Explore GPTs → Create a GPT

### Step 2: Set the Instructions

Paste this into the **Instructions** field:

```
You are a Coherence Network assistant. You help users take ideas from conception
to realization by interacting with the Coherence Network API.

Your workflow:
1. SHARE: Help the user articulate their idea and create it via POST /api/ideas
2. QUESTION: Surface what they don't know via POST /api/ideas/{id}/questions
3. SPEC: Help them plan the work via POST /api/spec-registry
4. WORK: Track contributions via POST /api/contributions/record
5. MEASURE: Update actual values via PATCH /api/ideas/{id}
6. PROVE: Show the full trace via GET /api/ideas/{id}

Always use the Coherence Network API for these operations. When creating ideas,
ask the user for: name, description, estimated value (how much impact if it works),
estimated cost (how much effort), and confidence (0-1, how sure they are).

When the user describes a problem or wish, proactively suggest creating an idea.
When they mention doing work, suggest recording a contribution.
When they report results, suggest updating measurements.

The API base is https://api.coherencycoin.com
For write operations, include header: X-API-Key: dev-key
```

### Step 3: Add the API Action

In the **Actions** section, click "Create new action" and paste:

**Authentication**: API Key, Header name: `X-API-Key`, Key: `dev-key`

**Schema** (paste this OpenAPI subset):

```yaml
openapi: 3.1.0
info:
  title: Coherence Network
  version: 1.0.0
  description: Idea realization platform — track ideas from conception to measured impact
servers:
  - url: https://api.coherencycoin.com
paths:
  /api/ideas:
    get:
      operationId: listIdeas
      summary: List ideas ranked by ROI
      parameters:
        - name: limit
          in: query
          schema: { type: integer, default: 20 }
      responses:
        '200':
          description: Ideas list
    post:
      operationId: createIdea
      summary: Create a new idea
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [name, description]
              properties:
                name: { type: string }
                description: { type: string }
                potential_value: { type: number, default: 10.0 }
                estimated_cost: { type: number, default: 5.0 }
                confidence: { type: number, default: 0.5 }
      responses:
        '201':
          description: Created
  /api/ideas/{idea_id}:
    get:
      operationId: getIdea
      summary: Get idea details
      parameters:
        - name: idea_id
          in: path
          required: true
          schema: { type: string }
      responses:
        '200':
          description: Idea detail
    patch:
      operationId: updateIdea
      summary: Update idea (stage, values, status)
      parameters:
        - name: idea_id
          in: path
          required: true
          schema: { type: string }
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                stage: { type: string, enum: [none, specced, implementing, testing, reviewing, complete] }
                manifestation_status: { type: string, enum: [none, partial, validated] }
                actual_value: { type: number }
                actual_cost: { type: number }
      responses:
        '200':
          description: Updated
  /api/ideas/{idea_id}/questions:
    post:
      operationId: addQuestion
      summary: Add an open question to an idea
      parameters:
        - name: idea_id
          in: path
          required: true
          schema: { type: string }
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [question]
              properties:
                question: { type: string }
                value_to_whole: { type: number, default: 10.0 }
                estimated_cost: { type: number, default: 2.0 }
      responses:
        '200':
          description: Question added
  /api/spec-registry:
    post:
      operationId: createSpec
      summary: Create a spec for an idea
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [title, summary]
              properties:
                spec_id: { type: string }
                title: { type: string }
                summary: { type: string }
                idea_id: { type: string }
      responses:
        '201':
          description: Spec created
  /api/contributions/record:
    post:
      operationId: recordContribution
      summary: Record a contribution to an idea
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [contribution_type, description]
              properties:
                contributor_display_name: { type: string }
                contribution_type: { type: string, enum: [code, docs, review, design, community, promotion] }
                description: { type: string }
                idea_id: { type: string }
                amount_cc: { type: number, default: 5.0 }
      responses:
        '201':
          description: Recorded
  /api/spec-registry/cards:
    get:
      operationId: listSpecCards
      summary: Spec dashboard with state counts
      parameters:
        - name: limit
          in: query
          schema: { type: integer, default: 50 }
      responses:
        '200':
          description: Spec cards
  /api/health:
    get:
      operationId: healthCheck
      summary: API health status
      responses:
        '200':
          description: Health
  /api/cc/supply:
    get:
      operationId: getCCSupply
      summary: Coherence Credit supply and coherence score
      responses:
        '200':
          description: CC supply info
  /api/governance/change-requests:
    post:
      operationId: proposeChange
      summary: Submit a governance change request
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [target_type, target_id, proposer_id]
              properties:
                target_type: { type: string, enum: [idea_create, idea_update, spec_create, spec_update, idea_add_question] }
                target_id: { type: string }
                proposer_id: { type: string }
                change_payload: { type: object }
                rationale: { type: string }
      responses:
        '201':
          description: Change request created
```

### Step 4: Test It

Try these prompts in your new Custom GPT:

> "I have an idea for a community tool library where neighbors share power tools instead of everyone buying their own."

The GPT will create the idea, ask you clarifying questions, help you estimate value and cost, and track it.

> "My neighbor just donated 5 power tools to the library. Record that."

The GPT will record the contribution with attribution.

> "We've had 30 tool checkouts in the first month. The estimated value of shared tools is $3,000 in avoided purchases."

The GPT will update the measurements and show the ROI.

---

## Option 2: Direct API from ChatGPT (No Custom GPT)

You can also just ask ChatGPT to call the API directly:

> "Call https://api.coherencycoin.com/api/ideas?limit=5 and show me the top ideas by potential value"

> "POST to https://api.coherencycoin.com/api/ideas with X-API-Key: dev-key header, and create an idea called 'Neighborhood Composting' with description 'Shared composting bins at the end of each block, volunteer rotation for turning'"

ChatGPT can make HTTP requests to the public API without any custom GPT setup.

---

## The Full Idea-to-Realization Flow from ChatGPT

```
You:  "I want to start a neighborhood composting program"
GPT:  [Creates idea via API] → "Created! ID: neighborhood-composting. What questions
       do you need to answer before starting?"

You:  "Where do we put the bins? Who turns the compost? What about smell?"
GPT:  [Adds 3 questions via API] → "Added 3 questions. The bin location question has
       the highest value-to-whole score. Let's answer that first."

You:  "I talked to the city — they said we can use the empty lot on Maple Street"
GPT:  [Answers question via API] → "Great! That de-risks the biggest question.
       Ready to write a plan?"

You:  "Yes, the plan is: 3 bins, volunteer rotation, weekly turning schedule"
GPT:  [Creates spec via API] → "Spec created: 'Composting Operations Plan'.
       Your idea is now at stage: specced."

You:  "My neighbor built the first bin last weekend"
GPT:  [Records contribution via API] → "Recorded: neighbor's bin construction,
       15 CC credited. Want to update the idea stage to 'implementing'?"

You:  "We've composted 200 pounds of food waste in the first month"
GPT:  [Updates measurements via API] → "Updated! Actual value: 35.0 (200 lbs
       diverted from landfill). ROI: 7x on effort invested. Idea status: validated."
```

Every step calls the real API. Every response is stored permanently. The idea's full journey — from spark to composting bin to 200 pounds of food waste diverted — is tracked and provable.

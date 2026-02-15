 Implementation Plan: Endpoint Wake-Up Button for Clinical Evidence Agent

       1. Problem Analysis

       The core problem is that HF Dedicated Endpoints (MedGemma and SapBERT) use "scale to zero" and take 2-5 minutes to cold-start.
       Currently, wake-up is entangled with query execution, causing SSE timeouts on Cloud Run. The solution is to separate wake-up from
       query execution with a dedicated UI flow.

       Key bugs identified during exploration:

       - /api/status SapBERT check is blocking: At line 154 of app.py, it calls search_qdrant.encode_via_hf_dedicated("test medical
       term") which has max_retries=3 and exponential backoff (10s, 20s, 40s = 70s total). This means /api/status can hang for over a
       minute if SapBERT is sleeping, making it useless as a quick status probe.
       - Frontend status bar references "Ollama" and "Qdrant" (line 375 and 467-476 of index.html): The JavaScript loadStatus() looks for
        d.ollama and d.qdrant in the response, but the backend returns qdrant_cloud, openrouter_api, sapbert_endpoint, and
       medgemma_endpoint. The status bar is completely non-functional in the cloud deployment.
       - MedGemma 503 is reported as ok: True, status: 'sleeping' (line 179 of app.py): This is semantically correct for "configured and
       reachable" but misleading for readiness. The status check correctly uses a 10-second timeout and does not retry, which is good --
       it returns fast.

       ---
       2. Design Decisions

       Q1: New /api/wakeup endpoint or reuse /api/status?

       Answer: Refactor /api/status into a fast, non-blocking probe, and add a new /api/wakeup endpoint.

       Rationale:
       - /api/status should return instantly (under 1 second) so it can be polled frequently. It should probe each endpoint with a short
       timeout (10s) and NO retries, reporting the raw state: ready, sleeping, error.
       - /api/wakeup is a fire-and-forget POST that sends a single "ping" request to each sleeping endpoint to trigger the auto-scaler.
       It does not wait for the endpoint to become ready. The frontend polls /api/status to detect when the endpoints transition from
       sleeping to ready.

       This design is simpler and more robust than having /api/wakeup be a long-polling SSE stream. The frontend controls the polling
       loop, and each /api/status call is cheap and fast.

       Q2: How to fix the slow SapBERT check?

       Answer: Replace the call to encode_via_hf_dedicated() with a direct HTTP POST with a 10-second timeout and NO retries, mirroring
       the existing MedGemma check pattern (lines 162-181 of app.py). The SapBERT endpoint at SAPBERT_ENDPOINT accepts a simple
       {"inputs": "test"} payload. A 200 means ready, 503 means sleeping, anything else is an error.

       Q3: How should frontend polling work during wake-up?

       Answer: Timer-based polling at 15-second intervals.

       Flow:
       1. User clicks "Wake Up" button.
       2. Frontend sends POST /api/wakeup (fire-and-forget, triggers the auto-scaler).
       3. Frontend starts a setInterval polling loop that calls GET /api/status every 15 seconds.
       4. A visible timer shows elapsed time (e.g., "Waking up... 45s elapsed").
       5. When all required endpoints report ready, polling stops, the Run button is enabled, and a success indicator appears.
       6. If 5 minutes pass without readiness, show an error message and stop polling.

       Q4: How should the status display be updated?

       Answer: Replace the two-dot status bar with a four-dot bar reflecting the actual cloud services:
       - Qdrant Cloud (database)
       - OpenRouter (E5 embeddings + translation)
       - SapBERT (atomic fact embeddings)
       - MedGemma (LLM inference)

       Each dot has three states: gray (checking), green (ready), yellow (sleeping), red (error).

       Q5: Should we guard runQuery() to re-check status before submitting?

       Answer: Yes. Before submitting the query, runQuery() should do a quick GET /api/status check. If required endpoints are not ready,
        it should abort with a message directing the user to wake up endpoints first. This prevents wasted Cloud Run request time on
       queries that will inevitably fail.

       ---
       3. Step-by-Step Implementation

       Phase 1: Backend Changes (app.py)

       Step 1.1: Fix /api/status to be fast and non-blocking

       Replace the SapBERT check (lines 152-157) with a direct HTTP probe, no retries:

       # HF Dedicated Endpoint (SapBERT embeddings) - fast probe, no retries
       sapbert_endpoint = os.getenv('SAPBERT_ENDPOINT')
       if sapbert_endpoint and HF_TOKEN:
           try:
               test_resp = http_requests.post(
                   sapbert_endpoint,
                   headers={
                       "Authorization": f"Bearer {HF_TOKEN}",
                       "Content-Type": "application/json"
                   },
                   json={"inputs": "test"},
                   timeout=10
               )
               if test_resp.status_code == 200:
                   result['sapbert_endpoint'] = {'ok': True, 'status': 'ready'}
               elif test_resp.status_code == 503:
                   result['sapbert_endpoint'] = {'ok': True, 'status': 'sleeping'}
               else:
                   result['sapbert_endpoint'] = {'ok': False, 'status_code': test_resp.status_code}
           except Exception as exc:
               result['sapbert_endpoint'] = {'ok': False, 'error': str(exc)}
       else:
           result['sapbert_endpoint'] = {'ok': False, 'configured': False}

       Similarly, normalize the MedGemma response format so both endpoints use the same status field vocabulary: ready, sleeping, or an
       error string.

       Remove the import search_qdrant for the SapBERT check -- the status endpoint should not import heavy modules for a simple HTTP
       probe.

       Step 1.2: Add /api/wakeup endpoint

       A POST endpoint that fires a single request to each sleeping endpoint to trigger the auto-scaler, then returns immediately. It
       does NOT wait for the endpoint to become ready.

       @app.route('/api/wakeup', methods=['POST'])
       def wakeup():
           """Send a ping to sleeping HF endpoints to trigger auto-scaler startup.
           Returns immediately -- does not wait for readiness.
           Frontend should poll /api/status to detect when endpoints become ready.
           """
           results = {}

           # Ping SapBERT
           sapbert_endpoint = os.getenv('SAPBERT_ENDPOINT')
           if sapbert_endpoint and HF_TOKEN:
               try:
                   resp = http_requests.post(
                       sapbert_endpoint,
                       headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"},
                       json={"inputs": "test"},
                       timeout=10
                   )
                   results['sapbert'] = 'ready' if resp.status_code == 200 else 'waking'
               except Exception:
                   results['sapbert'] = 'ping_sent'

           # Ping MedGemma
           if MEDGEMMA_ENDPOINT:
               try:
                   resp = http_requests.post(
                       f"{MEDGEMMA_ENDPOINT}/v1/chat/completions",
                       headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"},
                       json={"model": "tgi", "messages": [{"role": "user", "content": "test"}], "max_tokens": 5},
                       timeout=10
                   )
                   results['medgemma'] = 'ready' if resp.status_code == 200 else 'waking'
               except Exception:
                   results['medgemma'] = 'ping_sent'

           return jsonify(results)

       Step 1.3: Normalize /api/status response shape

       Ensure every service in the response has a consistent status field that the frontend can rely on:
       - "ready" -- good to go
       - "sleeping" -- endpoint exists but is scaled to zero
       - "error" -- endpoint is misconfigured or unreachable

       Keep ok: True/False for backward compatibility but add the normalized status string to every entry.

       Phase 2: Frontend Changes (templates/index.html)

       Step 2.1: Replace the status bar

       Replace lines 374-377 with four service indicators:

       <div id="status-bar">
         <span><span class="status-dot" id="dot-qdrant"></span>Qdrant <span id="lbl-qdrant">...</span></span>
         <span><span class="status-dot" id="dot-openrouter"></span>OpenRouter <span id="lbl-openrouter">...</span></span>
         <span><span class="status-dot" id="dot-sapbert"></span>SapBERT <span id="lbl-sapbert">...</span></span>
         <span><span class="status-dot" id="dot-medgemma"></span>MedGemma <span id="lbl-medgemma">...</span></span>
       </div>

       Add a CSS class for the sleeping state:
       .status-dot.sleeping { background: var(--warn); }

       Step 2.2: Rewrite loadStatus()

       Update the function to read the new response keys and set dot states:

       async function loadStatus() {
           try {
               const r = await fetch('/api/status');
               const d = await r.json();

               const setDot = (id, status, label) => {
                   const cls = status === 'ready' ? 'ok' : status === 'sleeping' ? 'sleeping' : 'err';
                   $(`dot-${id}`).className = `status-dot ${cls}`;
                   $(`lbl-${id}`).textContent = label;
               };

               // Qdrant Cloud
               if (d.qdrant_cloud) {
                   setDot('qdrant', d.qdrant_cloud.ok ? 'ready' : 'error',
                          d.qdrant_cloud.ok ? 'OK' : 'Error');
               }

               // OpenRouter
               if (d.openrouter_api) {
                   setDot('openrouter', d.openrouter_api.ok ? 'ready' : 'error',
                          d.openrouter_api.ok ? 'OK' : 'Error');
               }

               // SapBERT
               if (d.sapbert_endpoint) {
                   const st = d.sapbert_endpoint.status || (d.sapbert_endpoint.ok ? 'ready' : 'error');
                   setDot('sapbert', st, st === 'ready' ? 'Ready' : st === 'sleeping' ? 'Sleeping' : 'Error');
               }

               // MedGemma
               if (d.medgemma_endpoint) {
                   const st = d.medgemma_endpoint.status || (d.medgemma_endpoint.ok ? 'ready' : 'error');
                   setDot('medgemma', st, st === 'ready' ? 'Ready' : st === 'sleeping' ? 'Sleeping' : 'Error');
               }

               return d; // return data for readiness checks
           } catch(e) {
               console.error('status check failed', e);
               return null;
           }
       }

       Step 2.3: Add "Wake Up" button and timer UI

       Add a "Wake Up" button next to the Run button inside the .controls div. Also add a wake-up status area:

       <button id="wakeup-btn" style="display:none">起動</button>
       <div id="wakeup-status" style="display:none">
           <div class="spinner"></div>
           <span id="wakeup-text">エンドポイント起動中... 0秒</span>
       </div>

       Step 2.4: Implement wake-up flow and Run button gating

       Core JavaScript logic:

       let endpointStatus = { medgemma: 'unknown', sapbert: 'unknown' };
       let wakeupTimer = null;
       let wakeupStartTime = null;

       // On page load, check status and decide button states
       async function initStatus() {
           const d = await loadStatus();
           if (!d) return;

           endpointStatus.medgemma = d.medgemma_endpoint?.status || 'error';
           endpointStatus.sapbert = d.sapbert_endpoint?.status || 'error';

           updateButtonStates();
       }

       function updateButtonStates() {
           const mode = currentMode;
           const medReady = endpointStatus.medgemma === 'ready';
           const sapReady = endpointStatus.sapbert === 'ready';

           const canRun = (mode === 'direct') ? medReady : (medReady && sapReady);
           const needsWakeup = (endpointStatus.medgemma === 'sleeping' ||
                                (mode !== 'direct' && endpointStatus.sapbert === 'sleeping'));

           $('run-btn').disabled = !canRun;
           $('wakeup-btn').style.display = needsWakeup ? 'inline-block' : 'none';
       }

       async function wakeupEndpoints() {
           $('wakeup-btn').disabled = true;
           $('wakeup-status').style.display = 'flex';
           wakeupStartTime = Date.now();

           // Fire the wake-up ping
           try { await fetch('/api/wakeup', { method: 'POST' }); } catch(e) {}

           // Start polling
           wakeupTimer = setInterval(async () => {
               const elapsed = Math.floor((Date.now() - wakeupStartTime) / 1000);
               $('wakeup-text').textContent = `エンドポイント起動中... ${elapsed}秒`;

               // Timeout after 5 minutes
               if (elapsed > 300) {
                   clearInterval(wakeupTimer);
                   $('wakeup-status').style.display = 'none';
                   $('wakeup-btn').disabled = false;
                   showError('エンドポイントの起動がタイムアウトしました。再試行してください。');
                   return;
               }

               const d = await loadStatus();
               if (!d) return;

               endpointStatus.medgemma = d.medgemma_endpoint?.status || 'error';
               endpointStatus.sapbert = d.sapbert_endpoint?.status || 'error';

               updateButtonStates();

               // Check if we're done
               const mode = currentMode;
               const medReady = endpointStatus.medgemma === 'ready';
               const sapReady = endpointStatus.sapbert === 'ready';
               const allReady = (mode === 'direct') ? medReady : (medReady && sapReady);

               if (allReady) {
                   clearInterval(wakeupTimer);
                   $('wakeup-status').style.display = 'none';
                   $('wakeup-btn').style.display = 'none';
               }
           }, 15000);
       }

       $('wakeup-btn').addEventListener('click', wakeupEndpoints);

       Step 2.5: Guard runQuery() with a pre-flight status check

       At the top of runQuery(), before disabling the button and starting the SSE stream, add:

       async function runQuery() {
           const queryText = $('query-input').value.trim();
           if (!queryText) { showError('クエリを入力してください'); return; }

           // Pre-flight readiness check
           const d = await loadStatus();
           if (d) {
               const medReady = d.medgemma_endpoint?.status === 'ready';
               const sapReady = d.sapbert_endpoint?.status === 'ready';
               const mode = currentMode;

               if (mode === 'direct' && !medReady) {
                   showError('MedGemmaエンドポイントが起動していません。「起動」ボタンをクリックしてください。');
                   return;
               }
               if ((mode === 'rag' || mode === 'compare') && (!medReady || !sapReady)) {
                   showError('エンドポイントが起動していません。「起動」ボタンをクリックしてください。');
                   return;
               }
           }

           // ... existing runQuery logic continues ...
       }

       Step 2.6: Re-check button states on mode switch

       When the user clicks a mode button (Direct / RAG / Compare), call updateButtonStates() so the Run/Wake Up buttons reflect the
       requirements of the new mode:

       document.querySelectorAll('.mode-btn').forEach(btn => {
           btn.addEventListener('click', () => {
               document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
               btn.classList.add('active');
               currentMode = btn.dataset.mode;
               updateButtonStates();  // <-- add this
           });
       });

       Step 2.7: Style the Wake Up button

       Add CSS for the wake-up button, making it visually distinct (yellow/warning-toned) from the blue Run button:

       #wakeup-btn {
           padding: 8px 18px;
           background: var(--warn);
           border: none;
           border-radius: 6px;
           color: var(--bg);
           font-weight: 700;
           font-size: .9rem;
           cursor: pointer;
           transition: opacity .15s;
       }
       #wakeup-btn:disabled { opacity: .4; cursor: not-allowed; }

       #wakeup-status {
           font-size: .82rem;
           color: var(--warn);
           align-items: center;
           gap: 6px;
       }

       Phase 3: Call initStatus() on page load

       Replace the current loadStatus() call at line 481 with initStatus() which does both status display and button state management.

       ---
       4. Summary of Changes by File

       File: app.py
       Changes: Fix SapBERT check in /api/status (remove encode_via_hf_dedicated call, use direct HTTP probe). Normalize all status
       response fields.
         Add POST /api/wakeup endpoint.
       ────────────────────────────────────────
       File: templates/index.html
       Changes: Replace status bar HTML (4 services). Add .sleeping CSS class and #wakeup-btn styles. Rewrite loadStatus(). Add
       initStatus(),
         updateButtonStates(), wakeupEndpoints(). Gate runQuery() with pre-flight check. Bind mode switch to re-check. Add Wake Up button
        and timer
         elements.

       No changes needed to scripts/search_qdrant.py or scripts/medgemma_query.py -- the retry logic there is appropriate for actual
       query execution. The fix is only about the /api/status path not calling those retry-heavy functions.

       ---
       5. Sequence Diagram

       User clicks "Wake Up"
         |
         v
       Frontend: POST /api/wakeup  (fire-and-forget)
         |                            |
         |                            v
         |                    Backend pings SapBERT & MedGemma
         |                    (10s timeout, returns immediately)
         |                            |
         v                            v
       Frontend: starts setInterval(15s)
         |
         +--> GET /api/status  -->  Fast probe (10s timeout, no retries)
         |    Update dots & timer     Return {sapbert: {status: "sleeping"}, medgemma: {status: "ready"}}
         |
         +--> GET /api/status  -->  ...
         |    "45秒経過..."
         |
         +--> GET /api/status  -->  Return {sapbert: {status: "ready"}, medgemma: {status: "ready"}}
         |
         v
       Frontend: All ready! Enable Run button, hide wake-up UI.
         |
       User clicks "Run"
         |
         v
       Frontend: Pre-flight GET /api/status (confirm readiness)
         |
         v
       Frontend: POST /api/query (SSE stream -- endpoints are warm, no cold-start wait)

       ---
       6. Potential Challenges

       1. Race condition with HEALTHCHECK: The Dockerfile has HEALTHCHECK calling /api/status. The current broken SapBERT check with 70s
       retries could cause the healthcheck to hang. The fix to make /api/status fast (10s max per service) resolves this as a side
       effect.
       2. Cloud Run request timeout: Cloud Run has a 600s timeout configured. The wake-up polling is entirely client-side, so each
       individual /api/status request finishes in under 10 seconds -- well within limits.
       3. Both endpoints sleeping simultaneously: The user may need to wait for both. The UI handles this by tracking each independently
       and only enabling Run when the mode-appropriate set is ready.
       4. Endpoint goes back to sleep during long idle: If the user wakes endpoints, waits, but then does not run a query for a while,
       the endpoints may scale back to zero. The pre-flight check in runQuery() catches this and re-prompts the user.
       5. OpenRouter is always on: OpenRouter is a third-party API, not a dedicated endpoint, so it never sleeps. Only SapBERT and
       MedGemma need wake-up logic.

       ---
       Critical Files for Implementation

       - /Users/g150446/projects/clinical-evidence-agent/app.py - Fix /api/status SapBERT check, add /api/wakeup endpoint, normalize
       response format
       - /Users/g150446/projects/clinical-evidence-agent/templates/index.html - Replace status bar, add wake-up button/timer, rewrite
       loadStatus(), gate Run button, add polling logic
       - /Users/g150446/projects/clinical-evidence-agent/scripts/search_qdrant.py - Reference for encode_via_hf_dedicated() retry
       behavior (to understand what NOT to call from status), and for SAPBERT_ENDPOINT env var
       - /Users/g150446/projects/clinical-evidence-agent/Dockerfile - Verify HEALTHCHECK compatibility with the faster /api/status (no
       changes needed, but confirms the fix resolves the healthcheck hang)
       - /Users/g150446/projects/clinical-evidence-agent/deploy_cloud_run.sh - Reference for Cloud Run timeout configuration (confirms
       600s timeout is sufficient)
  ⎿  Done (7 tool uses · 62.5k tokens · 1m 55s)

                                                                                                                  04:42 PM <synthetic>
  ⎿  You've hit your limit · resets 7pm (Asia/Tokyo)

# In-app feedback agent flow

Authorized BrickBuilder users can request product changes from any page. The
control accepts a description and up to four screenshots, starts a GitHub
Copilot cloud-agent task from `staging`, and keeps revisions on the same pull
request branch.

## Event-driven flow

1. The browser calls the `change-request` Supabase Edge Function with the
   signed-in user's JWT. The function checks `change_request_access`; the
   browser never receives the allowlist.
2. Screenshots are placed in the private `change-request-images` bucket and
   passed to Copilot through four-hour signed URLs. They are deleted when the
   agent finishes and are not retained as product data.
3. Supabase stores GitHub's task ID. When the managed **Copilot cloud agent**
   workflow completes, `.github/workflows/change-request-vercel-preview.yml`
   verifies the PR's latest `copilot_work_finished` timeline event. The Edge
   Function links the task to GitHub's completed pull-request artifact, so the
   flow does not depend on text written by the agent.
4. Vercel's GitHub integration emits a successful Preview
   `deployment_status`. BrickBuilder's Vercel build already waits for the
   matching Railway PR environment and embeds its URL, so Vercel success is the
   single deploy-ready signal forwarded to Supabase.
5. The completion and deployment events are joined by exact commit SHA. If
   Vercel finished first, Copilot completion performs one GitHub lookup for the
   successful deployment and replays it. There is no cron job or polling loop.
6. Supabase creates a one-time magic-link token for the requesting account and
   emails the stable Vercel branch URL. The preview redeems the token, removes
   it from the address bar, and opens the matching request.
7. **Looks good — merge to staging** verifies the user, request, branch, PR,
   origin, and deployed SHA. It marks a draft PR ready when needed, merges it
   into `staging`, opens or reuses a `staging` to `main` PR, and emails that PR.
   It never merges `main`.

For requests submitted from the Expo shell, the same form sends `target=ios`.
After Copilot finishes, the workflow waits for the Vercel deployment of that
exact commit, injects its URL and signed request context into an EAS `feedback`
build, submits the build to an internal TestFlight group, and waits for Apple
to mark it available. Supabase then emails the requester the TestFlight and EAS
links. Approval or a revision request from that build must match its embedded
branch and commit SHA. Web requests continue to use the Vercel email flow.

## Setup

1. Link the Supabase CLI to project `smzdytfghwslpbqnwdov`, then apply
   `20260921000000_add_feedback_agent_flow.sql` and
   `20260921000001_add_feedback_email_allowlist.sql`, then
   `20260923000001_add_mobile_change_request_builds.sql`.
2. Deploy only the new function:

   ```bash
   supabase functions deploy change-request --no-verify-jwt \
     --project-ref smzdytfghwslpbqnwdov
   ```

3. Set these Supabase Edge secrets:

   - `CHANGE_REQUEST_GITHUB_TOKEN`: a fine-grained user token for this repository
     with metadata read and contents, pull requests, and Copilot requests read/write.
   - `CHANGE_REQUEST_GITHUB_REPO=jjohnson5253/brickbuilderai`
   - `CHANGE_REQUEST_GITHUB_EVENT_SECRET`: a new random value shared with GitHub Actions.
   - `RESEND_API_KEY`
   - `EMAIL_FROM`, for example `BrickBuilder <noreply@brickbuilder.ai>`.
   - `CHANGE_REQUEST_TESTFLIGHT_URL`, for example the public TestFlight join
     URL for App Store Connect app `6815050463`.

4. Add the same `CHANGE_REQUEST_GITHUB_EVENT_SECRET` value as a GitHub Actions
   repository secret. Add an `EXPO_TOKEN` repository secret and a
   `TESTFLIGHT_GROUP` repository variable containing the App Store Connect
   internal group name. Keep the Vercel GitHub integration enabled. Leave the
   repository variable `CHANGE_REQUEST_FLOW_ENABLED` unset until all setup is
   complete; this keeps deployment events from failing during installation.
5. Grant an existing Supabase Auth user access with privileged SQL:

   ```sql
   insert into public.change_request_access (user_id)
   select id from auth.users where lower(email) = lower('admin@example.com')
   on conflict (user_id) do nothing;
   ```

   Repeat for each authorized account. To pre-authorize someone before their
   Auth account exists, insert their normalized address into
   `change_request_email_access`. Remove access by deleting both applicable
   user-ID and email rows.
6. Set the GitHub Actions repository variable
   `CHANGE_REQUEST_FLOW_ENABLED=true` to activate both event handlers.

## Required deployment order

Merge the feature into `staging`, promote `staging` through a PR to `main`,
apply the migrations, deploy the Edge Function, set the Supabase and GitHub
secrets/variables, grant users access, and enable the repository variable last.
A workflow on a non-default branch does not reliably receive every repository
event, so the GitHub workflow must reach `main` before end-to-end testing.

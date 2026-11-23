# TickTick dashboard for TRMNL OG

A single-device BYOS server for the TRMNL OG. It uses the TickTick Open API, draws an 800×480 four-gray dashboard with a split time block header, stacked task cards, and a Daily Habits strip, and serves snapshots on a home-IP-restricted HTTPS endpoint.

The renderer uses antialiased Source Sans 3 with native grayscale levels 0, 85, 170, and 255 in a 2-bit grayscale PNG. The OG requires firmware 1.6.0 or newer for this format. Source Sans 3 is bundled under the [SIL Open Font License](app/fonts/OFL.txt). [TRMNL image format guide](https://docs.trmnl.com/go/diy/imagemagick-guide)

## Run locally

Use Python 3.12. The preview and unit tests use synthetic fixtures and need neither AWS access nor TickTick credentials.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
.venv/bin/python app/preview.py preview.png
.venv/bin/python app/preview.py preview-outage.png --outage
PYTHONPATH=app .venv/bin/python -m unittest discover -s tests -v
sam validate --lint --region us-east-1
sam build
```

## Verify the live TickTick mapping

Get a token in TickTick Web under **Settings → Account → API Token**. The [official TickTick CLI](https://www.npmjs.com/package/@ticktick/ticktick-cli) documents the routes used by this app. Find your Work and Time Blocking project IDs in TickTick's project list. The built-in Inbox ID may not appear in the project list. Identify it from the `projectId` on a known Inbox task returned by the official task filter, or inspect that field on an existing task in your signed-in TickTick browser session. Keep all real records out of saved fixtures.

### Save your project IDs and dashboard time zone

Fill in the three project IDs and `DASHBOARD_TIMEZONE` in the repository's `.env` file. If it is missing, create it with `cp -n .env.example .env`. Use an IANA time zone such as `Etc/UTC`.

```dotenv
TICKTICK_INBOX_ID=
TICKTICK_WORK_LIST_ID=
TICKTICK_TIME_BLOCKING_LIST_ID=
DASHBOARD_TIMEZONE=
```

The probe, live test, and deployment helper read this file automatically. Shell environment variables override individual saved values. The probe also accepts positional project IDs and `--timezone` overrides. Git ignores `.env`. Store the token in Keychain as described below.

### Store the local token in macOS Keychain

Open **Keychain Access** using Spotlight. Select the **login** keychain and choose **File → New Password Item** (⌘N). Enter `trmnl-ticktick` as the **Keychain Item Name**, `ticktick` as the **Account Name**, and paste the token into **Password**. If macOS asks whether `security` may access the item while running the probe or live test, choose **Allow**. [Apple Keychain Access guide](https://support.apple.com/guide/keychain-access/welcome/mac)

Both local tools use the Keychain item automatically. They honor `TICKTICK_TOKEN` first when it is supplied by your shell or a CI secret store. The probe also has a hidden interactive prompt for one-off use.

### Run the probe and compare with the app

Run this in your private terminal. Omit `--show-titles` to print counts only.

```sh
.venv/bin/python app/probe.py --show-titles
```

Compare Inbox and Work against TickTick in manual order, including due, overdue, undated, and future examples that already exist. Verify the Current Block and Upcoming Block against the Time Blocking list. An eligible block is an open timed task with a start and end (TickTick’s due date). Times use the dashboard time zone. The next block can be on a later day. A 200-row Inbox response is treated as potentially truncated.

Compare the first three eligible habits against today's view, checking section order and the habit order within each section. The dashboard requests check-ins from today through tomorrow's exclusive boundary in the dashboard time zone. If examples are available, confirm that completed and skipped habits are hidden and that partial check-ins below the goal stay eligible. Check that unused slots in the rendered Daily Habits strip stay blank.

Confirm all-day date behavior and any custom recurrence or grouping you use. Record outcomes without account content. If required behavior cannot be verified, pause before changing workflows or enabling the deployment.

### Run the live integration test

The fixture suite stays offline by default. The opt-in test reads your account’s current API responses, renders the dashboard, and checks the PNG format and size. The test prints only its result and sanitized API errors. Schema errors identify the failing section and failure type, for example `unexpected_schema/habit_checkins/invalid_type`.

```sh
TICKTICK_LIVE=1 PYTHONPATH=app \
  .venv/bin/python -m unittest discover -s tests -p test_ticktick_live.py -v
```

To save the dashboard for inspection, run the same test with `TICKTICK_PREVIEW_DIR` set to a private directory outside the repo. The PNG contains your live task and habit titles.

```sh
preview_dir=$(mktemp -d)
TICKTICK_LIVE=1 TICKTICK_PREVIEW_DIR="$preview_dir" PYTHONPATH=app \
  .venv/bin/python -m unittest discover -s tests -p test_ticktick_live.py -v
open "$preview_dir"
```

**Current verification status** — Unit tests use synthetic responses informed by the official CLI. Built-in Inbox access, archive/check-in semantics, and ordering still require an authenticated comparison.

## AWS deployment after explicit approval

Use AWS SAM and AWS CLI with an authorized account. The default estimate is for US East (N. Virginia). For a new deployment, create a standard Systems Manager **SecureString** under a dedicated name such as `/trmnl-ticktick/credentials` in the same region, using the default AWS managed SSM key. Enter a JSON object with one required field, `ticktick_token`, directly in the AWS console. Keep the token out of terminal history and chat.

For an existing deployment, keep the same SecureString name and value. The new handler ignores `device_key`. Leave it in place while you may roll back to a revision that requires it.

The deployment helper passes the saved settings to SAM as defaults for `InboxId`, `WorkListId`, `TimeBlockingListId`, and `DashboardTimezone`. Press Enter to accept them. Supply your home public IPv4 `/32` and the Parameter Store parameter **name** when SAM prompts. The `DeviceMac` parameter has been removed. Drop it from any saved SAM parameter overrides. Review the change set before executing it. To use a named AWS profile, add `--profile PROFILE` to the helper command.

API Gateway uses the public source IPv4 as the sole access gate for all BYOS routes. Any client reaching API Gateway from the allowed public IP can fetch dashboard images. Setup returns fixed firmware compatibility values, and the server ignores the `ID` and `Access-Token` headers.

```sh
sam build
.venv/bin/python deploy.py
aws cloudformation describe-stacks --region us-east-1 --stack-name trmnl-ticktick \
  --query 'Stacks[0].Outputs[?OutputKey==`ByosUrl`].OutputValue' --output text
```

Enter the output URL as the custom server base in the OG Wi-Fi setup and keep the `/byos` stage path. This is a dedicated BYOS dashboard. Return to TRMNL Cloud by selecting its hosted server in the device's Wi-Fi setup and reconnecting to your account. Firmware flashing is outside the deployment.

### Regional monthly estimate

Time Blocking adds one TickTick project read per display request. At 15-minute refreshes and 30 days, budget for 2,880 device wakes and up to 5,760 display and image requests. A planning estimate for `us-east-1` is **about $0.10–$0.15/month before free allowances** at normal traffic. Approximately $0.02 is REST API requests, $0.025 is Lambda at one second averaged over all invocations and 256 MB arm64, $0.02 is S3 requests and storage, and $0.01 covers standard SecureString KMS usage and modest logs. The rest allows for data transfer and variance. Actual execution time, log volume, data transfer, and rejected traffic can change the bill.

- [API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/)
- [Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [S3 pricing](https://aws.amazon.com/s3/pricing/)
- [Parameter Store encryption](https://docs.aws.amazon.com/systems-manager/latest/userguide/what-is-a-parameter.html)
- [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)

### Acceptance and operations

- From the home network, call `GET /api/setup`, `GET /api/display`, and `POST /api/log` without device headers and expect HTTP 200. Fetch `/images/setup.png` and the display image URL without device headers and confirm both return an 800×480 PNG. Verify setup and normal refresh on the physical OG, including retrieval on repeated wakes.
- During a window with no device traffic, request the setup image from cellular or another off-network connection. Expect HTTP 403. In CloudWatch, confirm the test did not increment Lambda invocations or produce a Lambda request log. Repeat against `/api/setup`, `/api/display`, and `/api/log`. Account for metrics publication delay.
- With approval, use a temporarily invalid TickTick token in the existing SecureString. Verify the OG shows the outage screen, restore the valid token, and verify recovery on the next wake. The function reads the parameter on each display request.
- To update the IP allowlist, rerun the deployment helper with the new `HomeCidr` and the existing values for the other parameters, then repeat the network checks. For application rollback, check out the last known-good revision in a separate checkout, run `sam build`, and run a guided deploy against the existing stack using its current configuration. If that revision predates the helper, use `sam deploy --guided`.
- Logs expire after 14 days. Image snapshots expire after three days. On approved teardown, `sam delete --region us-east-1 --stack-name trmnl-ticktick` deletes the stack and retains the private snapshot bucket. The bucket and the separately created SecureString can be deleted independently after approval.

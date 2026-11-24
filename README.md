# TickTick dashboard for TRMNL OG

A single-device BYOS server for the TRMNL OG. It uses the TickTick Open API, draws an 800×480 four-gray dashboard with a split time block header, task cards, and a Daily Habits strip, and serves snapshots on a home-IP-restricted HTTPS endpoint.

Work Tasks appears on refresh from 8:00 a.m. up to 5:00 p.m., Monday to Friday, in the configured dashboard time zone. After hours and on weekends, Todos fills the space.

The dashboard sleeps from 10:00 p.m. to 7:00 a.m. daily by default, in the configured dashboard time zone. At bedtime it shows the next refresh time and asks the device to wait until wake-up. A manual refresh during the window recalculates the remaining wait. The dashboard skips TickTick and credential reads during sleep and resumes its usual cadence at wake-up.

The renderer uses antialiased Source Sans 3 with native grayscale levels 0, 85, 170, and 255 in a 2-bit grayscale PNG. The OG requires firmware 1.6.0 or newer for this format. Source Sans 3 is bundled under the [SIL Open Font License](app/fonts/OFL.txt). [TRMNL image format guide](https://docs.trmnl.com/go/diy/imagemagick-guide)

## Run locally

Use Python 3.12. The preview and unit tests use synthetic fixtures and need neither AWS access nor TickTick credentials.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
PYTHONPATH=app .venv/bin/python scripts/preview.py preview.png
PYTHONPATH=app .venv/bin/python scripts/preview.py preview-after-hours.png --after-hours
PYTHONPATH=app .venv/bin/python scripts/preview.py preview-outage.png --outage
PYTHONPATH=app .venv/bin/python scripts/preview.py preview-sleep.png --sleep
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

The live test and deployment helper read this file automatically. Shell environment variables override individual saved values. Git ignores `.env`. Store the token in Keychain as described below.

### Store the local token in macOS Keychain

Open **Keychain Access** using Spotlight. Select the **login** keychain and choose **File → New Password Item** (⌘N). Enter `trmnl-ticktick` as the **Keychain Item Name**, `ticktick` as the **Account Name**, and paste the token into **Password**. If macOS asks whether `security` may access the item while running the live test, choose **Allow**. [Apple Keychain Access guide](https://support.apple.com/guide/keychain-access/welcome/mac)

The live test uses `TICKTICK_TOKEN` when supplied by your shell or a CI secret store. Otherwise, on macOS it reads the Keychain item automatically.

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

Use the saved preview for these checks against the signed-in TickTick app.

- Check that Inbox shows tasks due today or earlier in manual order. A 200-row Inbox response is treated as potentially truncated.
- During weekday work hours, check that Work shows open, top-level tasks from `Active` in manual order across all due dates, including undated tasks. After hours, check that Todos fills the available task space.
- Verify Current and Upcoming Block against the Time Blocking list. An eligible block is an open timed task with a start and end (TickTick’s due date). Times use the dashboard time zone, and the next block can be on a later day.
- Check the first three eligible habits in section order, then habit order within each section. Confirm that completed and skipped habits are hidden, partial check-ins below the goal stay eligible, and unused slots stay blank. The dashboard uses its configured time zone to determine today's check-ins.

Confirm all-day date behavior and any custom recurrence or grouping you use. Record outcomes without account content.

Synthetic Work Tasks tests passed for section membership, due-date coverage, manual order, and parent-task filtering. The official API returned one `Active` section for the configured Work list. The owner confirmed Work Tasks and normal dashboard behavior in the live preview and on the physical OG.

The owner confirmed built-in Inbox behavior, Current and Upcoming Block timing, habit ordering, and archive and check-in behavior against the signed-in TickTick app, including the applicable date, recurrence, and grouping checks. Live outage rendering and recovery remain pending.

## AWS deployment after explicit approval

Use AWS SAM and AWS CLI with an authorized account. The default estimate is for US East (N. Virginia). For a new deployment, create a standard Systems Manager **SecureString** under a dedicated name such as `/trmnl-ticktick/credentials` in the same region, using the default AWS managed SSM key. Enter a JSON object with one required field, `ticktick_token`, directly in the AWS console. Keep the token out of terminal history and chat.

For an existing deployment, keep the same SecureString name and value. The new handler ignores `device_key`. Leave it in place while you may roll back to a revision that requires it.

The deployment helper passes the saved settings to SAM as defaults for `InboxId`, `WorkListId`, `TimeBlockingListId`, and `DashboardTimezone`. Press Enter to accept them. Supply your home public IPv4 `/32` and the Parameter Store parameter **name** when SAM prompts. The `DeviceMac` parameter has been removed. Drop it from any saved SAM parameter overrides. Review the change set before executing it. To use a named AWS profile, add `--profile PROFILE` to the helper command.

Set `Bedtime` and `WakeTime` in guided SAM deployment using 24-hour `HH:MM` in the dashboard time zone. A window such as `22:00` to `22:15` ends the same evening. Set both to the same time to disable sleep. If a scheduled time repeats when clocks fall back, the first occurrence applies. If clocks skip it in spring, the transition moves forward by the size of the clock change.

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

- **Verified.** From the home network, call `GET /api/setup`, `GET /api/display`, and `POST /api/log` without device headers and expect HTTP 200. Fetch `/images/setup.png` and the display image URL without device headers and confirm both return an 800×480 PNG. Verify setup and normal refresh on the physical OG, including retrieval on repeated wakes.
- **Verified.** During a window with no device traffic, request the setup image from cellular or another off-network connection. Expect HTTP 403. In CloudWatch, confirm the test did not increment Lambda invocations or produce a Lambda request log. Repeat against `/api/setup`, `/api/display`, and `/api/log`. Account for metrics publication delay.
- **Pending.** With approval, use a temporarily invalid TickTick token in the existing SecureString. Verify that the live display endpoint returns the outage image and the OG shows it. Restore the valid token, verify that the live endpoint returns the normal dashboard, and verify recovery on the next OG wake. The function reads the parameter on each display request.
- **Verified.** The owner confirmed that the physical OG showed the sleep screen and automatically returned to the dashboard with a 10:00–10:15 p.m. sleep window. Overnight and daylight-saving timing were verified with fixtures.
- To update the IP allowlist, rerun the deployment helper with the new `HomeCidr` and the existing values for the other parameters, then repeat the network checks. For application rollback, check out the last known-good revision in a separate checkout, run `sam build`, and run a guided deploy against the existing stack using its current configuration. If that revision predates the helper, use `sam deploy --guided`.
- Logs expire after 14 days. Image snapshots expire after three days. On approved teardown, `sam delete --region us-east-1 --stack-name trmnl-ticktick` deletes the stack and retains the private snapshot bucket. The bucket and the separately created SecureString can be deleted independently after approval.

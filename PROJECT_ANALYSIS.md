# Project analysis after eSewa integration

## Current architecture

- **Backend:** Flask with server-rendered Jinja templates.
- **Authentication:** Flask-Login, password hashing, custom CSRF token checks, normal-user/admin roles.
- **Database:** Flask-SQLAlchemy + PostgreSQL with Flask-Migrate/Alembic migrations.
- **Prediction:** custom preprocessing pipeline + mini-batch SGD regressor trained from `UsedCars.csv` when the app starts.
- **Frontend:** custom CSS/JavaScript, vehicle brand/model autocomplete, estimator, metrics, profile and admin pages.
- **Marketplace:** a saved estimate can become a seller listing; active listings can be browsed and purchased by another authenticated user.
- **Payment:** eSewa ePay V2 UAT/production configuration, HMAC-SHA256 request signing, signed success-response verification, server-side transaction status check, Order/Payment records.

## Important issues found in the uploaded project

1. The new marketplace code contained a Python syntax error in the price filter, so the application could not compile.
2. Five templates referenced by marketplace/payment routes were missing: `sell_listing.html`, `listing_detail.html`, `payment_redirect.html`, `payment_result.html`, and `admin_marketplace.html`.
3. The old dummy eSewa checkout template was still present even though the new routes expected the real ePay flow.
4. UAT eSewa configuration required environment variables even though eSewa publishes test merchant credentials; this made a classroom/demo run unnecessarily difficult.
5. Payment failure handling treated every failure redirect as a definite failure even though eSewa can send pending transactions to the failure URL.
6. The status-check route could detect a completed transaction but could not finalize it if the normal success callback was missed.
7. The PostgreSQL driver was missing from `requirements.txt`.
8. The marketplace/profile additions did not have supporting styles, so even working pages would appear unfinished.

## What is now implemented

- Fixed the syntax error and verified all Python files compile.
- Added the missing marketplace/payment templates.
- Removed the stale dummy checkout template.
- Added a simple seller flow: saved prediction -> listing -> marketplace.
- Added buyer protection so a seller cannot buy their own listing.
- Added row locking/reservation before payment to reduce double-purchase risk.
- Added eSewa ePay V2 signed form generation.
- Added signed callback verification.
- Added eSewa server-side status verification.
- Only `COMPLETE` transactions become `PAID` / `SOLD`.
- `PENDING`/`AMBIGUOUS` payments stay unconfirmed.
- `CANCELED`/`NOT_FOUND` payments release the listing.
- Added a manual “Check payment status” fallback that can finalize a verified completed order.
- Added UAT test defaults and setup documentation.
- Added admin listing/transaction views and marketplace statistics.
- Added `psycopg2-binary` to project requirements.

## Remaining project work worth doing later

These are outside the requested simple eSewa integration but are the main technical items still worth addressing:

1. **Do not train the ML model on every app startup.** Persist the trained model and load it at runtime; retrain deliberately.
2. **Remove default production secrets.** `SECRET_KEY` and the default admin password should be mandatory environment variables outside local development.
3. **Move uploaded listing images to persistent storage for deployment.** Writing into `static/uploads` is not reliable on serverless hosts such as Vercel.
4. **Do not rely on appending to `UsedCars.csv` in production.** Serverless/local filesystem changes may be lost; store feedback in the database and retrain from persisted data.
5. **Add automated Flask route/database tests.** The current project has no full application test suite.
6. **Improve image validation.** Extension + browser MIME checks are useful but not enough for production; inspect actual image content.
7. **Use consistent timestamps.** Some models default to UTC while application-created records use Nepal-local naive timestamps.
8. **Split `app.py`.** Authentication, marketplace, admin, prediction, and payment routes should eventually move into Blueprints/services to reduce the single-file size.
9. **Update the final DOCX report.** The report files may still describe the earlier dummy-payment version and should be revised before submission.
10. **Production eSewa onboarding.** Replace UAT values with the merchant product code/secret supplied by eSewa and test HTTPS callback URLs before deployment.

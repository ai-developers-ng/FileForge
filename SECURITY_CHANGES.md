# Security Changes - Access Token Implementation

## Problem
The application had a critical security vulnerability where:
- `/history` page was public and showed all users' jobs
- Anyone could access/download any job by knowing the job_id
- No access control on job results and downloads

## Solution Implemented

### Backend Changes

#### 1. Database Schema (`ocr_engine/jobs.py`)
- ✅ Added `access_token` column to jobs table (migration to version 8)
- ✅ Generate secure 32-byte URL-safe token for each job
- ✅ `create_job()` now returns the access token
- ✅ `get_job()` now requires access_token parameter for verification

#### 2. API Endpoints (`app.py`)
- ✅ All job creation endpoints now return `access_token` in response
- ✅ Jobs stored in session for user's own history
- ✅ **Token required** for these endpoints:
  - `GET /api/jobs/<job_id>` - Requires `?token=` parameter or `X-Access-Token` header
  - `GET /api/jobs/<job_id>/stream` - Requires token
  - `GET /api/jobs/<job_id>/result` - Requires token
  - `GET /api/jobs/<job_id>/download/<fmt>` - Requires token
  - `GET /results/<job_id>` - Requires token in URL
- ✅ `/history` page now only shows jobs from current user's session

#### 3. Frontend Changes (`static/app.js`)
- ✅ Updated `streamJob()` to accept and use token parameter
- ✅ Updated `pollJob()` to accept and pass token to all API calls
- ✅ Jobs now store `accessToken` field
- ✅ All API calls include token in query string

### Security Benefits

1. **Access Control**: Only users with the correct token can access job data
2. **Session Isolation**: History page only shows current session's jobs
3. **Download Protection**: Files can only be downloaded with valid token
4. **URL Security**: Direct links include token, preventing unauthorized access

### API Response Changes

**Before:**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "result_url": "/api/jobs/uuid/result"
}
```

**After:**
```json
{
  "job_id": "uuid",
  "access_token": "secure-token-here",
  "status": "queued",
  "result_url": "/api/jobs/uuid/result?token=secure-token-here"
}
```

### URL Format Changes

**Before:** `https://yoursite.com/results/job-id`
**After:** `https://yoursite.com/results/job-id?token=access-token`

### Migration Notes

- Existing jobs in database will automatically get tokens assigned during migration
- Old URLs without tokens will be denied access (returns 403 Forbidden)
- Frontend automatically handles token management

### Testing Checklist

- [ ] Upload a file and verify token is returned
- [ ] Check that job status updates work with token
- [ ] Verify download links include token
- [ ] Confirm history page only shows your jobs
- [ ] Test that accessing job without token fails (403)
- [ ] Verify SSE streaming works with token

### Deployment Instructions

1. Upload updated files to VPS:
   - `app.py`
   - `ocr_engine/jobs.py`
   - `static/app.js`

2. Rebuild Docker container:
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

3. Database migration runs automatically on first start

4. Test the security:
   ```bash
   # This should fail (no token)
   curl https://yoursite.com/api/jobs/some-job-id

   # This should work (with valid token)
   curl "https://yoursite.com/api/jobs/some-job-id?token=your-token"
   ```

## Additional Recommendations

1. **Add HTTPS**: Tokens transmitted over HTTP can be intercepted
2. **Add rate limiting**: Already configured, but monitor for abuse
3. **Add token expiration**: Consider implementing TTL for tokens
4. **Add user authentication**: For persistent history across sessions
5. **Add audit logging**: Track access attempts for security monitoring

## Breaking Changes

⚠️ **Important**: All existing job URLs will stop working after this update.
Users will need to create new jobs to get new URLs with access tokens.

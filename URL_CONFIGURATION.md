# URL Configuration Changes

This document describes the changes made to replace hardcoded localhost:8000 references with configurable, relative URLs.

## Changes Made

### 1. Environment Configuration (.env)
- Added `BASE_URL` environment variable for centralized URL configuration
- Updated `GOOGLE_REDIRECT_URI` to use `${BASE_URL}` template
- Configuration now supports different environments (development, staging, production)

### 2. Python Files Updated

#### demo_analytics.py
- Changed hardcoded `BASE_URL = "http://localhost:8000"` to use environment variable
- Updated print statements to use relative URLs

#### diagnose_submissions.py
- Updated API calls to use environment-based URL configuration
- Changed hardcoded URLs in help text to relative URLs

#### start.py
- Added dynamic URL generation based on environment variables
- Supports SSL detection and custom domains
- Shows appropriate URLs based on configuration

### 3. Frontend Files
- ✅ Already using relative URLs in JavaScript files (`/api` endpoints)
- ✅ Templates already using relative URLs
- ✅ No hardcoded localhost references found in frontend

### 4. Configuration Script
Created `configure_url.py` to easily switch between environments:

```bash
# For development (default)
python configure_url.py development

# For staging
python configure_url.py staging

# For production
python configure_url.py production

# For custom URL
python configure_url.py custom https://myapp.mydomain.com
```

## Environment Variables

### Required Variables
- `BASE_URL`: The base URL for your application (e.g., `http://localhost:8000`)
- `GOOGLE_REDIRECT_URI`: OAuth redirect URI (automatically set to `${BASE_URL}/api/classroom/auth-callback`)

### Optional Variables for Advanced Configuration
- `APP_PORT`: Application port (default: 8000)
- `DOMAIN`: Custom domain (default: localhost)
- `SSL_CERT_PATH`: Path to SSL certificate (enables HTTPS)

## Benefits

1. **Environment Flexibility**: Easy switching between development, staging, and production
2. **Docker/Container Ready**: No hardcoded URLs that break in containers
3. **Deployment Ready**: Works with any domain/port configuration
4. **Reverse Proxy Compatible**: Works behind nginx, Apache, etc.
5. **SSL Ready**: Automatically detects and uses HTTPS when certificates are configured

## Migration Guide

If you have an existing deployment:

1. Set the `BASE_URL` environment variable in your `.env` file
2. Update any Google OAuth configuration to use the new redirect URI
3. Restart the application
4. All URLs will automatically use the new configuration

## Testing

To test the changes:

1. Update your `.env` file with the appropriate `BASE_URL`
2. Start the application: `python start.py`
3. Verify the URLs shown in the startup messages
4. Check that OAuth redirects work correctly
5. Confirm API calls from frontend work (should be automatic with relative URLs)

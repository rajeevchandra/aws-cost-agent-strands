@echo off
setlocal enabledelayedexpansion

REM ===== Config (edit if you changed names) =====
if "%FUNCTION_NAME%"=="" set "FUNCTION_NAME=cost-agent"
if "%ROLE_NAME%"=="" set "ROLE_NAME=lambda-cost-agent-role"
if "%API_NAME%"=="" set "API_NAME=cost-agent-api"

if not "%AWS_REGION%"=="" (
  set "REGION=%AWS_REGION%"
) else if not "%AWS_DEFAULT_REGION%"=="" (
  set "REGION=%AWS_DEFAULT_REGION%"
) else (
  set "REGION=us-east-1"
)
REM =============================================

echo === Pre-flight checks ===
where aws >nul 2>nul || (echo AWS CLI not found. Install AWS CLI v2 and run 'aws configure'. & exit /b 1)
echo Using region: %REGION%
echo Function: %FUNCTION_NAME%
echo Role: %ROLE_NAME%
echo API Name: %API_NAME%
echo.

REM ---- 1) Delete API Gateway (HTTP API) ----
echo === 1) Delete API Gateway (HTTP API) if present ===
set "API_ID="
for /f "delims=" %%A in ('aws apigatewayv2 get-apis --region %REGION% --query "Items[?Name=='%API_NAME%'].ApiId" --output text 2^>nul') do set "API_ID=%%A"

if defined API_ID (
  echo Found API ID: %API_ID% - deleting...
  aws apigatewayv2 delete-api --api-id %API_ID% --region %REGION% 1>nul 2>nul
  if errorlevel 1 (
    echo WARN: Could not delete API %API_ID%.
  ) else (
    echo Deleted API %API_ID%.
  )
) else (
  echo No API named "%API_NAME%" found - skipping.
)

echo.

REM ---- 2) Delete Lambda Function URL (if exists) ----
echo === 2) Delete Lambda Function URL (if exists) ===
aws lambda get-function-url-config --function-name %FUNCTION_NAME% --region %REGION% 1>nul 2>nul
if not errorlevel 1 (
  aws lambda delete-function-url-config --function-name %FUNCTION_NAME% --region %REGION% 1>nul 2>nul
  if errorlevel 1 (
    echo WARN: Could not delete Function URL.
  ) else (
    echo Deleted Function URL for %FUNCTION_NAME%.
  )
) else (
  echo No Function URL configured - skipping.
)

echo.

REM ---- 3) Delete Lambda Function ----
echo === 3) Delete Lambda Function ===
aws lambda get-function --function-name %FUNCTION_NAME% --region %REGION% 1>nul 2>nul
if not errorlevel 1 (
  aws lambda delete-function --function-name %FUNCTION_NAME% --region %REGION% 1>nul 2>nul
  if errorlevel 1 (
    echo WARN: Could not delete Lambda function.
  ) else (
    echo Deleted Lambda function %FUNCTION_NAME%.
  )
) else (
  echo Lambda function not found - skipping.
)

echo.

REM ---- 4) Delete CloudWatch Log Group (optional) ----
echo === 4) Delete CloudWatch Log Group ===
set "LOG_GROUP=/aws/lambda/%FUNCTION_NAME%"
aws logs describe-log-groups --log-group-name-prefix "%LOG_GROUP%" --region %REGION% --query "logGroups[?logGroupName=='%LOG_GROUP%'].logGroupName" --output text 1>nul 2>nul
if not errorlevel 1 (
  aws logs delete-log-group --log-group-name "%LOG_GROUP%" --region %REGION% 1>nul 2>nul
  if errorlevel 1 (
    echo WARN: Could not delete log group %LOG_GROUP%.
  ) else (
    echo Deleted log group %LOG_GROUP%.
  )
) else (
  echo Log group not found - skipping.
)

echo.

REM ---- 5) Detach policies and delete IAM Role ----
echo === 5) Detach policies and delete IAM Role ===
REM Inline policy from deploy script
aws iam delete-role-policy --role-name %ROLE_NAME% --policy-name bedrock-ce-access 1>nul 2>nul
REM Managed policy (ok if not attached)
aws iam detach-role-policy --role-name %ROLE_NAME% --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 1>nul 2>nul

aws iam get-role --role-name %ROLE_NAME% 1>nul 2>nul
if not errorlevel 1 (
  aws iam delete-role --role-name %ROLE_NAME% 1>nul 2>nul
  if errorlevel 1 (
    echo WARN: Could not delete role %ROLE_NAME%. Make sure no policies/boundaries remain.
  ) else (
    echo Deleted IAM role %ROLE_NAME%.
  )
) else (
  echo IAM role not found - skipping.
)

echo.
echo ✅ Cleanup complete.
exit /b 0

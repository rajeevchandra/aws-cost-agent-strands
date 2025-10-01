@echo off
setlocal enabledelayedexpansion

REM ======= EDIT THESE THREE =======
set "ACCOUNT_ID="
set "REGION=us-east-1"
set "ZIP_PATH=C:\Users\deepi\Downloads\strands-mcp-lambda-with-strands.zip"
REM =================================

set "FUNCTION_NAME=cost-agent"
set "ROLE_NAME=lambda-cost-agent-role"
set "BEDROCK_MODEL_ID=openai.gpt-oss-120b-1:0"
set "GROUP_BY=SERVICE,LINKED_ACCOUNT"
set "METRIC=UnblendedCost"
set "GRANULARITY=MONTHLY"
set "USE_FUNCTION_URL=false"

echo === Pre-flight checks ===
where aws >nul 2>nul || (echo AWS CLI not found in PATH. Install AWS CLI v2 and run 'aws configure'. & exit /b 1)
if not exist "%ZIP_PATH%" (echo ZIP not found: %ZIP_PATH% & exit /b 1)

set "AWS_REGION=%REGION%"
set "AWS_DEFAULT_REGION=%REGION%"

set "TRUST_JSON={\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"lambda.amazonaws.com\"},\"Action\":\"sts:AssumeRole\"}]}"
set "POLICY_JSON={\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"BedrockInvoke\",\"Effect\":\"Allow\",\"Action\":[\"bedrock:InvokeModel\",\"bedrock:InvokeModelWithResponseStream\"],\"Resource\":\"*\"},{\"Sid\":\"CostExplorerRead\",\"Effect\":\"Allow\",\"Action\":[\"ce:GetCostAndUsage\",\"ce:GetDimensionValues\",\"ce:GetCostForecast\"],\"Resource\":\"*\"}]}"

echo:
echo === Create / ensure IAM role: %ROLE_NAME% ===
set "NEW_ROLE=0"
aws iam get-role --role-name %ROLE_NAME% >nul 2>nul
if errorlevel 1 (
  aws iam create-role --role-name %ROLE_NAME% --assume-role-policy-document "%TRUST_JSON%" || goto :err
  set "NEW_ROLE=1"
) else (
  aws iam update-assume-role-policy --role-name %ROLE_NAME% --policy-document "%TRUST_JSON%" || goto :err
)
aws iam attach-role-policy --role-name %ROLE_NAME% --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole >nul 2>nul
aws iam put-role-policy --role-name %ROLE_NAME% --policy-name bedrock-ce-access --policy-document "%POLICY_JSON%" || goto :err

if "%NEW_ROLE%"=="1" (
  echo Waiting for IAM role to propagate...
  ping -n 10 127.0.0.1 >nul
) else (
  ping -n 5 127.0.0.1 >nul
)

set "ROLE_ARN=arn:aws:iam::%ACCOUNT_ID%:role/%ROLE_NAME%"

echo:
echo === Create / update Lambda: %FUNCTION_NAME% ===
set "FN_EXISTS=0"
aws lambda get-function --function-name %FUNCTION_NAME% >nul 2>nul && set "FN_EXISTS=1"

if "%FN_EXISTS%"=="1" (
  aws lambda update-function-code --function-name %FUNCTION_NAME% --zip-file fileb://%ZIP_PATH% || goto :err
) else (
  set "ATTEMPTS=0"
  :create_retry
  set /a ATTEMPTS+=1
  echo Attempt !ATTEMPTS!/5 to create function...
  aws lambda create-function --function-name %FUNCTION_NAME% ^
    --runtime python3.11 --handler lambda_handler.lambda_handler ^
    --role %ROLE_ARN% --timeout 60 --memory-size 1536 ^
    --zip-file fileb://%ZIP_PATH%
  if errorlevel 1 (
    if !ATTEMPTS! LSS 5 (
      echo Create failed; sleeping then retrying...
      ping -n 8 127.0.0.1 >nul
      goto :create_retry
    ) else (
      goto :err
    )
  )
)

REM === Configure Lambda environment (write JSON without BOM) ===
set "WORK=%TEMP%\cost-agent-deploy"
if not exist "%WORK%" mkdir "%WORK%"
set "ENV_JSON=%WORK%\env.json"

powershell -NoProfile -Command "$o=@{Variables=@{BEDROCK_REGION='%REGION%';BEDROCK_MODEL_ID='%BEDROCK_MODEL_ID%';MCP_COMMAND='python mcp_cost_server_safe.py';GROUP_BY='%GROUP_BY%';METRIC='%METRIC%';GRANULARITY='%GRANULARITY%'}}; $o | ConvertTo-Json -Compress | Out-File -FilePath '%ENV_JSON%' -Encoding ASCII"

aws lambda update-function-configuration --function-name %FUNCTION_NAME% --environment file://%ENV_JSON% || goto :err


aws lambda update-function-configuration --function-name %FUNCTION_NAME% --environment file://%ENV_JSON% || goto :err


aws lambda update-function-configuration --function-name %FUNCTION_NAME% --environment file://%ENV_JSON% || goto :err

echo:
if /i "%USE_FUNCTION_URL%"=="true" (
  echo === Create / fetch Function URL ===
  set "FURL="
  for /f "delims=" %%A in ('aws lambda get-function-url-config --function-name %FUNCTION_NAME% --query "FunctionUrl" --output text 2^>nul') do set "FURL=%%A"
  if not defined FURL (
    aws lambda create-function-url-config --function-name %FUNCTION_NAME% --auth-type NONE || goto :err
    aws lambda add-permission --function-name %FUNCTION_NAME% --statement-id allow-public-furl --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE >nul 2>nul
    for /f "delims=" %%A in ('aws lambda get-function-url-config --function-name %FUNCTION_NAME% --query "FunctionUrl" --output text') do set "FURL=%%A"
  )
  echo:
  echo ✅ Function URL:
  echo %FURL%
  echo Try:
  echo curl -X POST "%FURL%" -H "Content-Type: application/json" -d "{\"query\":\"What is my spend from 2025-09-01 to 2025-10-01?\"}"
) else (
  echo === Create / fetch API Gateway HTTP API ===
  set "API_ENDPOINT="
  set "API_ID="

  for /f "delims=" %%A in ('aws apigatewayv2 create-api --name %FUNCTION_NAME%-api --protocol-type HTTP --target arn:aws:lambda:%REGION%:%ACCOUNT_ID%:function:%FUNCTION_NAME% --query "ApiEndpoint" --output text 2^>nul') do set "API_ENDPOINT=%%A"
  for /f "delims=" %%A in ('aws apigatewayv2 get-apis --query "Items[?Name==`'%FUNCTION_NAME%-api'`].ApiId" --output text') do set "API_ID=%%A"
  if not defined API_ENDPOINT (
    for /f "delims=" %%A in ('aws apigatewayv2 get-apis --query "Items[?Name==`'%FUNCTION_NAME%-api'`].ApiEndpoint" --output text') do set "API_ENDPOINT=%%A"
  )

  aws lambda add-permission --function-name %FUNCTION_NAME% --statement-id apigw-invoke --action lambda:InvokeFunction --principal apigateway.amazonaws.com ^
    --source-arn arn:aws:execute-api:%REGION%:%ACCOUNT_ID%:%API_ID%/*/*/* >nul 2>nul

  echo:
  echo ✅ API Gateway endpoint:
  echo %API_ENDPOINT%/
  echo Try:
  echo curl -X POST "%API_ENDPOINT%/" -H "Content-Type: application/json" -d "{\"query\":\"Forecast my spend from 2025-10-01 to 2025-11-01\"}"
)

echo:
echo ✅ Done.
exit /b 0

:err
echo:
echo ❌ Deployment failed. See the error above.
exit /b 1

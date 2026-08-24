# Complete Guide to Setting Up and Testing EcoScheduler Backend

## Step 1: Set Up AWS Account Resources

First, you need to set up the required AWS resources in both your master and customer accounts.

### Master Account Setup

1. Create the master account CloudFormation stack:

```bash
cd backend
aws cloudformation deploy \
    --template-file infra/master-account.yml \
    --stack-name EcoScheduler-Master-Resources \
    --capabilities CAPABILITY_NAMED_IAM
```

2. Get your master account ID:

```bash
MASTER_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Your master account ID is: $MASTER_ACCOUNT_ID"
```

### Customer Account Setup

For each AWS account you want to manage EC2 instances in:

1. Configure AWS CLI with credentials for the customer account:

```bash
aws configure --profile customer1
```

2. Deploy the customer account CloudFormation template:

```bash
aws cloudformation deploy \
    --template-file infra/customer-account-role.yml \
    --stack-name EcoScheduler-CrossAccount-Role \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides "MasterAccountId=$MASTER_ACCOUNT_ID" \
    --profile customer1
```

## Step 2: Set Up Local Environment

1. Install Node.js dependencies:

```bash
cd backend
npm install
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables:

```bash
# Create .env file for development
cat > .env << EOL
# EcoScheduler Environment Variables
STAGE=dev
REGION=us-east-1
JWT_SECRET=your-jwt-secret-key-change-in-production
MASTER_ACCOUNT_ID=$MASTER_ACCOUNT_ID
EOL
```

## Step 3: Deploy Backend with Serverless Framework

1. Install Serverless Framework globally if you haven't already:

```bash
npm install -g serverless
```

2. Deploy the application:

```bash
# Switch back to master account credentials if needed
aws configure

# Deploy with Serverless Framework
npm run deploy:dev
# Or directly:
serverless deploy --stage dev
```

3. Note the API Gateway URL from the output:

```
endpoints:
  POST - https://abcdef123.execute-api.us-east-1.amazonaws.com/dev/auth/login
  POST - https://abcdef123.execute-api.us-east-1.amazonaws.com/dev/auth/register
  ...
```

Save this URL for testing later: `https://abcdef123.execute-api.us-east-1.amazonaws.com/dev`

## Step 4: Create an Admin User

1. Run the admin user creation script:

```bash
# Create admin user
python ./scripts/create_admin_user.py --stage dev --region us-east-1
```

2. Enter the required information:
   - Admin email address (e.g., `admin@example.com`)
   - Full name (e.g., `Admin User`)
   - Password (at least 8 characters)
   - AWS account IDs to manage (comma-separated list of your customer accounts)

## Step 5: Test the APIs

1. Use the provided test script to verify all API endpoints:

```bash
python ./scripts/test_api.py \
    --api-url https://abcdef123.execute-api.us-east-1.amazonaws.com/dev \
    --email admin@example.com \
    --password your-password \
    --account-id 123456789012 \
    --instance-id i-0123456789abcdef0
```

The script will run through all the key API endpoints:
- Authentication (login)
- User management
- Schedule creation, listing, retrieval, updating, and deletion
- EC2 instance listing
- EC2 instance start/stop operations (with confirmation prompts)
- Savings reports

2. Alternatively, test individual endpoints using curl or Postman:

```bash
# Login and get token
TOKEN=$(curl -s -X POST \
  https://abcdef123.execute-api.us-east-1.amazonaws.com/dev/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "admin@example.com", "password": "your-password"}' \
  | jq -r '.token')

# Test getting user profile
curl -X GET \
  https://abcdef123.execute-api.us-east-1.amazonaws.com/dev/users/me \
  -H "Authorization: Bearer $TOKEN"
```

## Step 6: Local Development (Optional)

For local development and testing without deploying to AWS:

1. Install and start DynamoDB local:

```bash
npm run dynamodb:install
npm run dynamodb:start
```

2. Start the API Gateway locally:

```bash
npm run offline
```

3. In another terminal, create a test admin user in the local database:

```bash
USERS_TABLE=EcoScheduler-Users \
SCHEDULES_TABLE=EcoScheduler-Schedules \
SAVINGS_TABLE=EcoScheduler-Savings \
EXCEPTIONS_TABLE=EcoScheduler-Exceptions \
python ./scripts/create_admin_user.py
```

4. Test the local API using the API testing script:

```bash
python ./scripts/test_api.py \
    --api-url http://localhost:3000 \
    --email admin@example.com \
    --password your-password
```

## Step 7: Common Issues and Troubleshooting

### DynamoDB Table Issues

If you encounter DynamoDB table errors:

```bash
# Check if tables exist
aws dynamodb list-tables

# Describe a specific table
aws dynamodb describe-table --table-name eco-scheduler-users-dev
```

### Authentication Issues

If you have JWT authentication problems:

1. Check that your JWT_SECRET is correctly set
2. Verify the token has not expired
3. Ensure proper Authorization header format: `Bearer <token>`

### Cross-Account Access Issues

If EC2 operations fail across accounts:

1. Verify the cross-account role exists in the customer account:

```bash
aws iam get-role --role-name EcoScheduler-CrossAccount-Role --profile customer1
```

2. Confirm trust relationship is correct:

```bash
aws iam get-role --role-name EcoScheduler-CrossAccount-Role --profile customer1 --query 'Role.AssumeRolePolicyDocument'
```

3. Test assume role manually:

```bash
aws sts assume-role \
    --role-arn arn:aws:iam::CUSTOMER_ACCOUNT_ID:role/EcoScheduler-CrossAccount-Role \
    --role-session-name TestSession
```

### Serverless Deployment Issues

If serverless deployment fails:

```bash
# Remove and redeploy
serverless remove --stage dev
serverless deploy --stage dev

# Check CloudFormation stack events
aws cloudformation describe-stack-events --stack-name eco-scheduler-dev
```

## Next Steps

Once you have the backend successfully deployed and tested:

1. **Add More Customer Accounts**: Deploy the cross-account role to additional AWS accounts
2. **Set Up Scheduled Cost Calculation**: Create an EventBridge rule to run the savings calculation daily
3. **Develop the Frontend**: Create a web interface to manage the schedules and view savings reports
4. **Set Up Monitoring**: Create CloudWatch dashboards to monitor API usage and Lambda executions
5. **Implement Email Notifications**: Add SNS/SES integration for schedule failure notifications
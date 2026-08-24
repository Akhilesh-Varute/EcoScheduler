# Getting Started with EcoScheduler

This guide will walk you through setting up the EcoScheduler backend, configuring your AWS accounts, and testing the APIs.

## Prerequisites

- AWS CLI installed and configured with appropriate credentials
- Node.js 14+ and npm
- Python 3.10+
- Serverless Framework CLI (`npm install -g serverless`)

## Step 1: Initial Setup

Clone the repository and navigate to the backend directory:

```bash
git clone https://github.com/yourusername/eco-scheduler.git
cd eco-scheduler/backend
```

## Step 2: Install Dependencies

Install both Node.js and Python dependencies:

```bash
# Install Node.js dependencies
npm install

# Install Python dependencies
pip install -r requirements.txt
```

## Step 3: Set Up AWS Resources

### Master Account Setup

1. Deploy the master account CloudFormation template:

```bash
aws cloudformation deploy \
    --template-file infra/master-account.yml \
    --stack-name EcoScheduler-Master-Resources \
    --capabilities CAPABILITY_NAMED_IAM
```

2. Note the outputs from the stack, which include IAM role ARNs and API keys.

### Customer Account Setup

For each AWS account you want to manage with EcoScheduler, deploy the cross-account role:

```bash
# Get your master account ID
MASTER_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Deploy the cross-account role template in each customer account
aws cloudformation deploy \
    --template-file infra/customer-account-role.yml \
    --stack-name EcoScheduler-CrossAccount-Role \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides "MasterAccountId=$MASTER_ACCOUNT_ID"
```

## Step 4: Configure Environment Variables

Create a `.env` file with the following content:

```bash
# EcoScheduler Environment Variables
STAGE=dev
REGION=us-east-1
JWT_SECRET=your-jwt-secret-key-here
MASTER_ACCOUNT_ID=your-master-account-id
```

You can also use the setup script to automatically create this file:

```bash
# Generate .env file with default values
./setup.sh
```

## Step 5: Deploy with Serverless Framework

Deploy the backend to AWS:

```bash
# Deploy to development stage
npm run deploy:dev

# Or use serverless directly
serverless deploy --stage dev
```

This will create all required AWS resources, including:
- Lambda functions
- API Gateway endpoints
- DynamoDB tables
- IAM roles and policies
- EventBridge rules

## Step 6: Create an Admin User

Use the provided script to create an admin user:

```bash
# Create admin user
npm run create-admin

# Or run the Python script directly
python ./scripts/create_admin_user.py
```

You'll be prompted to enter:
- Admin email address
- Full name
- Password
- AWS account IDs to manage (comma-separated)

## Step 7: Local Development (Optional)

For local development, you can use the following commands:

```bash
# Start local DynamoDB
npm run dynamodb:install
npm run dynamodb:start

# Start API Gateway locally
npm run offline
```

This allows you to test your API endpoints locally before deploying to AWS.

## Step 8: Testing Your First API

Once the backend is deployed, you can test the APIs using curl or Postman:

1. First, authenticate to get a JWT token:

```bash
curl -X POST \
  https://your-api-gateway-id.execute-api.us-east-1.amazonaws.com/dev/auth/login \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "your-admin-email@example.com",
    "password": "your-password"
  }'
```

This will return a JWT token that you'll need for all other API calls.

2. Test getting your user profile:

```bash
curl -X GET \
  https://your-api-gateway-id.execute-api.us-east-1.amazonaws.com/dev/users/me \
  -H 'Authorization: Bearer YOUR_JWT_TOKEN'
```

3. Create a schedule:

```bash
curl -X POST \
  https://your-api-gateway-id.execute-api.us-east-1.amazonaws.com/dev/schedules \
  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Business Hours",
    "accountId": "123456789012",
    "instanceIds": ["i-1234567890abcdef0"],
    "startCron": "0 8 * * 1-5",
    "stopCron": "0 18 * * 1-5",
    "timezone": "America/New_York"
  }'
```

## Troubleshooting

If you encounter any issues, check the CloudWatch Logs for your Lambda functions:

```bash
# View logs for a specific function
serverless logs -f FunctionName -t
```

Or view the logs in the AWS Management Console under:
- CloudWatch > Log Groups > /aws/lambda/eco-scheduler-{stage}-{function-name}
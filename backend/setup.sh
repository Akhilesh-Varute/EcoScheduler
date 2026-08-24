#!/bin/bash
# EcoScheduler Setup Script

set -e

print_header() {
    echo "======================="
    echo "$1"
    echo "======================="
}

# Initialize variables
STAGE=${STAGE:-dev}
REGION=${REGION:-us-east-1}
JWT_SECRET=${JWT_SECRET:-"secret-key-change-me-in-production"}

# Check AWS CLI is installed
if ! [ -x "$(command -v aws)" ]; then
  echo 'Error: aws CLI is not installed.' >&2
  exit 1
fi

# Check if we're already logged in to AWS
aws sts get-caller-identity > /dev/null 2>&1 || {
    echo "Please configure AWS CLI with 'aws configure' before running this script"
    exit 1
}

print_header "Creating CloudFormation stacks"

# Get the current account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Current Account ID: $ACCOUNT_ID"

# Deploy master account template
echo "Deploying master account CloudFormation template..."
aws cloudformation deploy \
    --template-file infra/master-account.yml \
    --stack-name EcoScheduler-Master-Resources \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION

# Print the outputs from the CloudFormation stack
echo "Getting CloudFormation outputs..."
aws cloudformation describe-stacks \
    --stack-name EcoScheduler-Master-Resources \
    --query 'Stacks[0].Outputs' \
    --region $REGION

print_header "Setting up environment variables"

# Create .env file for Serverless Framework
cat > .env << EOL
# EcoScheduler Environment Variables
STAGE=${STAGE}
REGION=${REGION}
JWT_SECRET=${JWT_SECRET}
MASTER_ACCOUNT_ID=${ACCOUNT_ID}
EOL

echo ".env file created with following content:"
cat .env

print_header "Installing dependencies"

# Install NPM dependencies
npm install

# Install Python dependencies
pip install -r requirements.txt

print_header "Deploying Serverless Resources"

# Deploy with Serverless Framework
echo "Deploying backend with Serverless Framework..."
npm run deploy:${STAGE}

print_header "Setup Complete"
echo "EcoScheduler backend has been deployed to stage: ${STAGE}"
echo "API URL can be found in the Serverless output above"
echo ""
echo "To set up a customer account, run the following in each AWS account you want to manage:"
echo ""
echo "aws cloudformation deploy \\"
echo "    --template-file infra/customer-account-role.yml \\"
echo "    --stack-name EcoScheduler-CrossAccount-Role \\"
echo "    --capabilities CAPABILITY_NAMED_IAM \\"
echo "    --parameter-overrides MasterAccountId=${ACCOUNT_ID} \\"
echo "    --region $REGION"
echo ""
echo "Next steps:"
echo "1. Create an admin user in the application (see README.md)"
echo "2. Add your AWS accounts in the UI"
echo "3. Create your first schedule"
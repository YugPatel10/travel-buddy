#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { StorageStack } from "../lib/storage-stack";
import { AuthStack } from "../lib/auth-stack";
import { ApiStack } from "../lib/api-stack";

const app = new cdk.App();

const storageStack = new StorageStack(app, "TravelBuddyStorage", {
  description: "Travel Buddy — S3 and DynamoDB storage resources",
});

const authStack = new AuthStack(app, "TravelBuddyAuth", {
  description: "Travel Buddy — Cognito authentication resources",
});

new ApiStack(app, "TravelBuddyApi", {
  description: "Travel Buddy — API Gateway and Lambda functions",
  userPool: authStack.userPool,
  tripsTable: storageStack.tripsTable,
  scoutResultsTable: storageStack.scoutResultsTable,
  documentsTable: storageStack.documentsTable,
  agentRunsTable: storageStack.agentRunsTable,
  documentsBucket: storageStack.documentsBucket,
});

app.synth();

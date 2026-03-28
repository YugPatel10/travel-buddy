import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3n from "aws-cdk-lib/aws-s3-notifications";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as path from "path";
import { Construct } from "constructs";

export class StorageStack extends cdk.Stack {
  public readonly documentsBucket: s3.Bucket;
  public readonly tripsTable: dynamodb.Table;
  public readonly scoutResultsTable: dynamodb.Table;
  public readonly documentsTable: dynamodb.Table;
  public readonly agentRunsTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Parameter for Pinecone API key (pass at deploy time or via Secrets Manager)
    new cdk.CfnParameter(this, "PineconeApiKey", {
      type: "String",
      description: "Pinecone API key for vector storage",
      default: "",
      noEcho: true,
    });

    this.documentsBucket = new s3.Bucket(this, "DocumentsBucket", {
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      enforceSSL: true,

      cors: [
        {
          allowedOrigins: ["*"],
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.PUT,
            s3.HttpMethods.POST,
          ],
          allowedHeaders: ["*"],
          exposedHeaders: ["ETag"],
          maxAge: 3600,
        },
      ],

      lifecycleRules: [
        {
          id: "AbortIncompleteMultipartUploads",
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
        },
        {
          id: "TransitionToIA",
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
        },
        {
          id: "ExpireOldVersions",
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
      ],
    });

    new cdk.CfnOutput(this, "DocumentsBucketName", {
      value: this.documentsBucket.bucketName,
      description: "S3 bucket for travel document uploads",
    });

    // --- Document Processor Lambda (triggered by S3 uploads) ---

    const backendRoot = path.join(__dirname, "..", "..", "backend");

    const documentProcessorLambda = new lambda.Function(
      this,
      "DocumentProcessorLambda",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: "handler.handler",
        code: lambda.Code.fromAsset(
          path.join(backendRoot, "lambdas", "document_processor")
        ),
        environment: {
          DOCUMENTS_BUCKET: this.documentsBucket.bucketName,
        },
        timeout: cdk.Duration.minutes(5),
        memorySize: 512,
      }
    );

    // Grant the Lambda read access to the S3 bucket
    this.documentsBucket.grantRead(documentProcessorLambda);

    // Trigger the Lambda on object creation in the uploads/ prefix
    this.documentsBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(documentProcessorLambda),
      { prefix: "uploads/" }
    );

    // Trips table: PK = USER#<userId>, SK = TRIP#<tripId>
    this.tripsTable = new dynamodb.Table(this, "TripsTable", {
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // ScoutResults table: PK = TRIP#<tripId>, SK = SCOUT#<timestamp>#<type>
    // TTL on old results (30 days)
    this.scoutResultsTable = new dynamodb.Table(this, "ScoutResultsTable", {
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      timeToLiveAttribute: "TTL",
    });

    // Documents table: PK = USER#<userId>, SK = DOC#<docId>
    this.documentsTable = new dynamodb.Table(this, "DocumentsTable", {
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // Grant the document processor Lambda access to the Documents table
    this.documentsTable.grantReadWriteData(documentProcessorLambda);
    documentProcessorLambda.addEnvironment(
      "DOCUMENTS_TABLE",
      this.documentsTable.tableName
    );

    // Grant Textract permissions for document text extraction
    documentProcessorLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["textract:AnalyzeDocument", "textract:DetectDocumentText"],
        resources: ["*"],
      })
    );

    // Grant Bedrock permissions for Claude (parsing) and Titan Embed v2 (embeddings)
    documentProcessorLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:InvokeModel"],
        resources: [
          `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0`,
          `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
        ],
      })
    );

    // Pinecone API key and index name (resolved at deploy time via env vars)
    documentProcessorLambda.addEnvironment(
      "PINECONE_API_KEY",
      cdk.Fn.ref("PineconeApiKey")
    );
    documentProcessorLambda.addEnvironment(
      "PINECONE_INDEX_NAME",
      "travel-buddy"
    );

    // AgentRuns table: PK = TRIP#<tripId>, SK = RUN#<runId>
    this.agentRunsTable = new dynamodb.Table(this, "AgentRunsTable", {
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      timeToLiveAttribute: "TTL",
    });

    new cdk.CfnOutput(this, "TripsTableName", {
      value: this.tripsTable.tableName,
    });
    new cdk.CfnOutput(this, "ScoutResultsTableName", {
      value: this.scoutResultsTable.tableName,
    });
    new cdk.CfnOutput(this, "DocumentsTableName", {
      value: this.documentsTable.tableName,
    });
    new cdk.CfnOutput(this, "AgentRunsTableName", {
      value: this.agentRunsTable.tableName,
    });
  }
}

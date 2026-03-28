import * as cdk from "aws-cdk-lib";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as path from "path";
import { Construct } from "constructs";

export interface ApiStackProps extends cdk.StackProps {
  userPool: cognito.IUserPool;
  tripsTable: dynamodb.ITable;
  scoutResultsTable: dynamodb.ITable;
  documentsTable: dynamodb.ITable;
  agentRunsTable: dynamodb.ITable;
  documentsBucket: s3.IBucket;
}

export class ApiStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const backendRoot = path.join(__dirname, "..", "..", "backend");

    // REST API Gateway
    this.api = new apigateway.RestApi(this, "TravelBuddyApi", {
      restApiName: "travel-buddy-api",
      description: "Travel Buddy REST API",
      deployOptions: {
        stageName: "prod",
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          "Content-Type",
          "Authorization",
          "X-Amz-Date",
          "X-Api-Key",
        ],
      },
    });

    // Cognito authorizer
    const authorizer = new apigateway.CognitoUserPoolsAuthorizer(
      this,
      "TravelBuddyCognitoAuthorizer",
      {
        cognitoUserPools: [props.userPool],
        identitySource: "method.request.header.Authorization",
      }
    );

    const authMethodOptions: apigateway.MethodOptions = {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    };

    // Shared Lambda environment variables
    const sharedEnv: Record<string, string> = {
      TRIPS_TABLE: props.tripsTable.tableName,
      SCOUT_RESULTS_TABLE: props.scoutResultsTable.tableName,
      DOCUMENTS_TABLE: props.documentsTable.tableName,
      AGENT_RUNS_TABLE: props.agentRunsTable.tableName,
      DOCUMENTS_BUCKET: props.documentsBucket.bucketName,
    };

    // --- Lambda Functions ---

    const tripLambda = new lambda.Function(this, "TripLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(path.join(backendRoot, "lambdas", "trip")),
      environment: sharedEnv,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    const documentLambda = new lambda.Function(this, "DocumentLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(backendRoot, "lambdas", "document")
      ),
      environment: sharedEnv,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    const chatLambda = new lambda.Function(this, "ChatLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(path.join(backendRoot, "lambdas", "chat")),
      environment: sharedEnv,
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
    });

    const briefingLambda = new lambda.Function(this, "BriefingLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(backendRoot, "lambdas", "briefing")
      ),
      environment: sharedEnv,
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
    });

    // --- IAM Permissions ---

    // Trip Lambda: read/write Trips + ScoutResults tables
    props.tripsTable.grantReadWriteData(tripLambda);
    props.scoutResultsTable.grantReadData(tripLambda);

    // Document Lambda: read/write Documents table + S3 bucket
    props.documentsTable.grantReadWriteData(documentLambda);
    props.documentsBucket.grantReadWrite(documentLambda);

    // Chat Lambda: read all tables
    props.tripsTable.grantReadData(chatLambda);
    props.documentsTable.grantReadData(chatLambda);
    props.agentRunsTable.grantReadData(chatLambda);

    // Briefing Lambda: read Trips, ScoutResults, AgentRuns
    props.tripsTable.grantReadData(briefingLambda);
    props.scoutResultsTable.grantReadData(briefingLambda);
    props.agentRunsTable.grantReadData(briefingLambda);

    // --- API Routes ---

    const trips = this.api.root.addResource("trips");
    const singleTrip = trips.addResource("{tripId}");
    const scouts = singleTrip.addResource("scouts");
    const scoutTrends = scouts.addResource("trends");
    const briefing = singleTrip.addResource("briefing");
    const pois = singleTrip.addResource("pois");
    const poisSearch = pois.addResource("search");

    const documents = this.api.root.addResource("documents");
    const uploadUrl = documents.addResource("upload-url");
    const singleDocument = documents.addResource("{docId}");

    const chat = this.api.root.addResource("chat");
    const chatHistory = chat.addResource("{tripId}");

    const tripIntegration = new apigateway.LambdaIntegration(tripLambda);
    const documentIntegration = new apigateway.LambdaIntegration(documentLambda);
    const chatIntegration = new apigateway.LambdaIntegration(chatLambda);
    const briefingIntegration = new apigateway.LambdaIntegration(briefingLambda);

    // Trip routes
    trips.addMethod("POST", tripIntegration, authMethodOptions);
    trips.addMethod("GET", tripIntegration, authMethodOptions);
    singleTrip.addMethod("GET", tripIntegration, authMethodOptions);
    singleTrip.addMethod("PUT", tripIntegration, authMethodOptions);
    singleTrip.addMethod("DELETE", tripIntegration, authMethodOptions);

    // Scout routes (served by trip lambda)
    scouts.addMethod("GET", tripIntegration, authMethodOptions);
    scoutTrends.addMethod("GET", tripIntegration, authMethodOptions);

    // Document routes
    uploadUrl.addMethod("POST", documentIntegration, authMethodOptions);
    documents.addMethod("GET", documentIntegration, authMethodOptions);
    singleDocument.addMethod("GET", documentIntegration, authMethodOptions);

    // Chat routes
    chat.addMethod("POST", chatIntegration, authMethodOptions);
    chatHistory.addMethod("GET", chatIntegration, authMethodOptions);

    // Briefing routes
    briefing.addMethod("GET", briefingIntegration, authMethodOptions);
    briefing.addMethod("POST", briefingIntegration, authMethodOptions);

    // POI routes (served by briefing lambda)
    pois.addMethod("GET", briefingIntegration, authMethodOptions);
    poisSearch.addMethod("POST", briefingIntegration, authMethodOptions);

    // --- Outputs ---

    new cdk.CfnOutput(this, "ApiUrl", {
      value: this.api.url,
      description: "Travel Buddy API Gateway URL",
    });
  }
}

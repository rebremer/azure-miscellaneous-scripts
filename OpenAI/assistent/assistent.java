import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

public class OpenAIRequestJava {
    private static final String endpoint = "ai-rebremerai744852064041.openai.azure.com";
    private static final String apiKey = "995cdb2a8e6b4fa18d739489fe001ca3";
    private static final HttpClient client = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_2)
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    public static void main(String[] args) throws Exception {
        // Create Assistant
        String assistantId = createAssistant();
        System.out.println(assistantId);

        // Create a Thread
        String threadId = createThread();
        System.out.println(threadId);

        // Add a User Question to the Thread
        addUserQuestion(threadId);

        // Run the Thread
        String runId = runThread(threadId, assistantId);
        System.out.println(runId);

        // Check Run Status
        checkRunStatus(threadId, runId);

        // Get Thread Messages
        getThreadMessages(threadId);
    }

    private static String createAssistant() throws Exception {
        String url = String.format("https://%s/openai/assistants?api-version=2024-05-01-preview", endpoint);
        String requestBody = "{\"instructions\": \"python code creator dsafdasf\", \"name\": \"testrb\", \"tools\": [], \"model\": \"gpt-4\", \"tool_resources\": {\"code_interpreter\": {\"file_ids\": [\"assistant-s8grUFK2VIT08OyTfvXdFdJG\"]}}, \"temperature\": 1, \"top_p\": 1}";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        JsonObject jsonResponse = JsonParser.parseString(response.body()).getAsJsonObject();
        return jsonResponse.get("id").getAsString();
    }

    private static String createThread() throws Exception {
        String url = String.format("https://%s/openai/threads?api-version=2024-05-01-preview", endpoint);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString("{}"))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        JsonObject jsonResponse = JsonParser.parseString(response.body()).getAsJsonObject();
        return jsonResponse.get("id").getAsString();
    }

    private static void addUserQuestion(String threadId) throws Exception {
        String url = String.format("https://%s/openai/threads/%s/messages?api-version=2024-05-01-preview", endpoint, threadId);
        String requestBody = "{\"role\": \"user\", \"content\": \"give me python code to store data on adlsgen2\"}";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .build();

        client.send(request, HttpResponse.BodyHandlers.ofString());
    }

    private static String runThread(String threadId, String assistantId) throws Exception {
        String url = String.format("https://%s/openai/threads/%s/runs?api-version=2024-05-01-preview", endpoint, threadId);
        String requestBody = String.format("{\"assistant_id\": \"%s\"}", assistantId);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        JsonObject jsonResponse = JsonParser.parseString(response.body()).getAsJsonObject();
        return jsonResponse.get("id").getAsString();
    }

    private static void checkRunStatus(String threadId, String runId) throws Exception {
        String url;
        HttpResponse<String> response;
        JsonObject jsonResponse;
        String status;

        do {
            url = String.format("https://%s/openai/threads/%s/runs/%s?api-version=2024-05-01-preview", endpoint, threadId, runId);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Authorization", "Bearer " + apiKey)
                    .build();

            response = client.send(request, HttpResponse.BodyHandlers.ofString());
            jsonResponse = JsonParser.parseString(response.body()).getAsJsonObject();
            status = jsonResponse.get("status").getAsString();
            System.out.println(status);

            Thread.sleep(1000); // Sleep for 1 second
        } while ("queued".equals(status) || "in_progress".equals(status) || "cancelling".equals(status));
    }

    private static void getThreadMessages(String threadId) throws Exception {
        String url = String.format("https://%s/openai/threads/%s/messages?api-version=2024-05-01-preview", endpoint, threadId);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Authorization", "Bearer " + apiKey)
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println(response.body());
    }
}

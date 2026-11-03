using System.Security.Cryptography.X509Certificates;
using Microsoft.Extensions.FileProviders;

var projectRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
var certificatePath = Path.Combine(projectRoot, "certs", "localhost.crt");
var keyPath = Path.Combine(projectRoot, "certs", "localhost.key");
using var pemCertificate = X509Certificate2.CreateFromPemFile(certificatePath, keyPath);
using var certificate = X509CertificateLoader.LoadPkcs12(
    pemCertificate.Export(X509ContentType.Pfx), null, X509KeyStorageFlags.UserKeySet | X509KeyStorageFlags.PersistKeySet);
Console.WriteLine($"localhost cert: private-key={certificate.HasPrivateKey}, expires={certificate.NotAfter:O}");

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
builder.Logging.AddConsole();
builder.WebHost.ConfigureKestrel(options =>
    options.ListenLocalhost(5500, listen => listen.UseHttps(certificate)));

var app = builder.Build();
using var apiClient = new HttpClient();
app.Use(async (context, next) =>
{
    var path = context.Request.Path.Value ?? "/";
    if (path.Equals("/api", StringComparison.OrdinalIgnoreCase) ||
        path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase))
    {
        var target = new Uri($"http://127.0.0.1:5000{context.Request.Path}{context.Request.QueryString}");
        using var proxiedRequest = new HttpRequestMessage(new HttpMethod(context.Request.Method), target);
        if (context.Request.ContentLength > 0 || context.Request.Headers.ContainsKey("Transfer-Encoding"))
            proxiedRequest.Content = new StreamContent(context.Request.Body);
        foreach (var header in context.Request.Headers)
        {
            if (header.Key.Equals("Host", StringComparison.OrdinalIgnoreCase) ||
                header.Key.Equals("Connection", StringComparison.OrdinalIgnoreCase) ||
                header.Key.Equals("Transfer-Encoding", StringComparison.OrdinalIgnoreCase))
                continue;
            if (!proxiedRequest.Headers.TryAddWithoutValidation(header.Key, header.Value.ToArray()))
                proxiedRequest.Content?.Headers.TryAddWithoutValidation(header.Key, header.Value.ToArray());
        }
        using var apiResponse = await apiClient.SendAsync(
            proxiedRequest, HttpCompletionOption.ResponseHeadersRead, context.RequestAborted);
        context.Response.StatusCode = (int)apiResponse.StatusCode;
        foreach (var header in apiResponse.Headers)
            context.Response.Headers[header.Key] = header.Value.ToArray();
        foreach (var header in apiResponse.Content.Headers)
            context.Response.Headers[header.Key] = header.Value.ToArray();
        context.Response.Headers.Remove("transfer-encoding");
        await apiResponse.Content.CopyToAsync(context.Response.Body, context.RequestAborted);
        return;
    }
    var blocked = path.Split('/', StringSplitOptions.RemoveEmptyEntries)
        .Any(segment => segment.StartsWith('.') ||
            segment.Equals("certs", StringComparison.OrdinalIgnoreCase) ||
            segment.Equals("secure-host", StringComparison.OrdinalIgnoreCase) ||
            segment.Equals("tests", StringComparison.OrdinalIgnoreCase));
    var extension = Path.GetExtension(path);
    var publicExtensions = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "", ".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".mp4" };
    if (blocked || !publicExtensions.Contains(extension))
    {
        context.Response.StatusCode = StatusCodes.Status404NotFound;
        return;
    }
    context.Response.Headers["X-Content-Type-Options"] = "nosniff";
    context.Response.Headers["Referrer-Policy"] = "strict-origin-when-cross-origin";
    context.Response.Headers["X-Frame-Options"] = "DENY";
    context.Response.Headers["Content-Security-Policy"] = "default-src 'self' https: data: blob:; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:; img-src 'self' https: data: blob:; connect-src 'self' https: wss:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";
    await next();
});

app.UseDefaultFiles(new DefaultFilesOptions
{
    FileProvider = new PhysicalFileProvider(projectRoot)
});
app.UseStaticFiles(new StaticFileOptions
{
    FileProvider = new PhysicalFileProvider(projectRoot),
    OnPrepareResponse = context =>
    {
        context.Context.Response.Headers["Cache-Control"] = "no-cache";
    }
});

app.Run();

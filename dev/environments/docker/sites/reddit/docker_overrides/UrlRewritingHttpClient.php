<?php

namespace App\HttpClient;

use Symfony\Contracts\HttpClient\HttpClientInterface;
use Symfony\Contracts\HttpClient\ResponseInterface;
use Symfony\Contracts\HttpClient\ResponseStreamInterface;

/**
 * HTTP client decorator that rewrites external URLs to internal localhost address.
 *
 * This allows the Reddit container to handle submission URLs that reference
 * any external hostname/port by rewriting them to the internal container address.
 * Supports any protocol (http/https), hostname, and port combination.
 */
class UrlRewritingHttpClient implements HttpClientInterface
{
    private HttpClientInterface $client;

    public function __construct(HttpClientInterface $client)
    {
        $this->client = $client;
    }

    public function request(string $method, string $url, array $options = []): ResponseInterface
    {
        // Rewrite any external URL (any host, any port) to internal container address
        // Examples:
        //   http://localhost:9999/post/123 -> http://localhost/post/123
        //   http://reddit.example.com/post/123 -> http://localhost/post/123
        //   https://192.168.1.100:8443/post/123 -> http://localhost/post/123
        $rewrittenUrl = preg_replace('/^https?:\/\/[^\/]+\//', 'http://localhost/', $url);

        return $this->client->request($method, $rewrittenUrl, $options);
    }

    public function stream($responses, float $timeout = null): ResponseStreamInterface
    {
        return $this->client->stream($responses, $timeout);
    }

    public function withOptions(array $options): static
    {
        $clone = clone $this;
        $clone->client = $this->client->withOptions($options);
        return $clone;
    }
}

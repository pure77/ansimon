package com.nmdw.ansimon.global.config;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ExternalApiPropertiesTest {

    @Test
    void exposesConfiguredExternalApiEndpoints() {
        ExternalApiProperties properties = new ExternalApiProperties(
                new ExternalApiProperties.Endpoint("https://kma.example.test", "kma-key"),
                new ExternalApiProperties.Endpoint("https://shelter.example.test", "shelter-key"),
                new ExternalApiProperties.Endpoint("https://tmap.example.test", "tmap-key"),
                new ExternalApiProperties.Endpoint("http://localhost:8000", ""),
                new ExternalApiProperties.Endpoint("http://localhost:7000", "connection-key")
        );

        assertThat(properties.kma().baseUrl()).isEqualTo("https://kma.example.test");
        assertThat(properties.tmap().apiKey()).isEqualTo("tmap-key");
        assertThat(properties.ml().baseUrl()).isEqualTo("http://localhost:8000");
        assertThat(properties.connection().baseUrl()).isEqualTo("http://localhost:7000");
        assertThat(properties.connection().apiKey()).isEqualTo("connection-key");
    }
}

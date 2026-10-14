package com.nmdw.ansimon.global.config;

import com.nmdw.ansimon.global.error.ExternalServiceException;
import com.nmdw.ansimon.global.webclient.WebClientErrorMapper;
import io.netty.channel.ChannelOption;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.util.StringUtils;
import org.springframework.web.reactive.function.BodyExtractor;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFilterFunction;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.support.ClientResponseWrapper;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;

/**
 * 기상청·쉼터·TMAP·ML·전화 연동에 사용할 서비스별 {@link WebClient} Bean을 구성합니다.
 * 외부 설정에서 기본 주소와 인증 정보를 받고, 공통 연결·응답 타임아웃과 실패 변환 필터를 모든 클라이언트에 동일하게 적용합니다.
 * 도메인 어댑터는 이 Bean을 사용해 외부 통신 정책을 재구현하지 않고도 안전한 예외 계약을 얻습니다.
 */
@Configuration
@EnableConfigurationProperties({ExternalApiProperties.class, WebClientTimeoutProperties.class,
        ConnectionWebClientProperties.class})
public class WebClientConfig {

    private final WebClientErrorMapper errorMapper = new WebClientErrorMapper();

    @Bean
    public WebClient kmaWebClient(WebClient.Builder builder, ExternalApiProperties properties,
                                  WebClientTimeoutProperties timeoutProperties) {
        return build(builder, properties.kma(), timeoutProperties, "kma");
    }

    @Bean
    public WebClient shelterWebClient(WebClient.Builder builder, ExternalApiProperties properties,
                                      WebClientTimeoutProperties timeoutProperties) {
        return build(builder, properties.shelter(), timeoutProperties, "shelter");
    }

    @Bean
    public WebClient tmapWebClient(WebClient.Builder builder, ExternalApiProperties properties,
                                   WebClientTimeoutProperties timeoutProperties) {
        return build(builder, properties.tmap(), timeoutProperties, "tmap");
    }

    @Bean
    public WebClient mlWebClient(WebClient.Builder builder, ExternalApiProperties properties,
                                 WebClientTimeoutProperties timeoutProperties) {
        return build(builder, properties.ml(), timeoutProperties, "ml");
    }

    @Bean
    public WebClient connectionWebClient(WebClient.Builder builder, ExternalApiProperties properties,
                                         ConnectionWebClientProperties timeoutProperties) {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS,
                        Math.toIntExact(timeoutProperties.getConnectionTimeout().toMillis()))
                .responseTimeout(timeoutProperties.getResponseTimeout());
        WebClient.Builder configuredBuilder = builder.clone()
                .baseUrl(properties.connection().baseUrl())
                .clientConnector(new ReactorClientHttpConnector(httpClient));
        if (StringUtils.hasText(properties.connection().apiKey())) {
            configuredBuilder.defaultHeader("Authorization", "Bearer " + properties.connection().apiKey());
        }
        return configuredBuilder.build();
    }

    private WebClient build(WebClient.Builder builder, ExternalApiProperties.Endpoint endpoint,
                            WebClientTimeoutProperties timeoutProperties, String serviceId) {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS,
                        Math.toIntExact(timeoutProperties.getConnectionTimeout().toMillis()))
                .responseTimeout(timeoutProperties.getResponseTimeout());
        WebClient.Builder configuredBuilder = builder.clone()
                .baseUrl(endpoint.baseUrl())
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .filter(mapExternalErrors(serviceId));
        if (StringUtils.hasText(endpoint.apiKey())) {
            configuredBuilder.defaultHeader("Authorization", "Bearer " + endpoint.apiKey());
        }
        return configuredBuilder.build();
    }

    private ExchangeFilterFunction mapExternalErrors(String serviceId) {
        return (request, next) -> {
            WebClientErrorMapper.ExternalRequestContext context =
                    WebClientErrorMapper.ExternalRequestContext.forService(serviceId, request.method());
            return next.exchange(request)
                    .flatMap(response -> {
                        ClientResponse mappedResponse = new ErrorMappingClientResponse(response, errorMapper, context);
                        return response.statusCode().isError()
                                ? mappedResponse.releaseBody().then(Mono.<ClientResponse>error(
                                        errorMapper.forStatus(response.statusCode(), context)))
                                : Mono.just(mappedResponse);
                    })
                    .onErrorMap(throwable -> !(throwable instanceof ExternalServiceException),
                            throwable -> errorMapper.forFailure(throwable, context));
        };
    }

    /**
     * 응답 본문을 읽는 중 발생한 네트워크·디코딩 실패까지 공통 외부 서비스 예외로 정규화하는 응답 래퍼입니다.
     * {@link WebClientConfig}의 필터가 성공 응답에 감싸 반환하며, 이미 변환된 예외는 유지해 오류 분류가 중복되지 않게 합니다.
     * 외부 API의 세부 실패 원인은 노출하지 않고 {@link WebClientErrorMapper}가 정한 안전한 오류 코드로 연결합니다.
     */
    private static final class ErrorMappingClientResponse extends ClientResponseWrapper {

        private final WebClientErrorMapper errorMapper;
        private final WebClientErrorMapper.ExternalRequestContext context;

        private ErrorMappingClientResponse(ClientResponse response, WebClientErrorMapper errorMapper,
                                           WebClientErrorMapper.ExternalRequestContext context) {
            super(response);
            this.errorMapper = errorMapper;
            this.context = context;
        }

        @Override
        public <T> Mono<T> bodyToMono(Class<? extends T> elementClass) {
            return map(super.bodyToMono(elementClass));
        }

        @Override
        public <T> Mono<T> bodyToMono(ParameterizedTypeReference<T> elementTypeRef) {
            return map(super.bodyToMono(elementTypeRef));
        }

        @Override
        public <T> Flux<T> bodyToFlux(Class<? extends T> elementClass) {
            return map(super.bodyToFlux(elementClass));
        }

        @Override
        public <T> Flux<T> bodyToFlux(ParameterizedTypeReference<T> elementTypeRef) {
            return map(super.bodyToFlux(elementTypeRef));
        }

        @Override
        public Mono<Void> releaseBody() {
            return map(super.releaseBody());
        }

        @Override
        @SuppressWarnings("unchecked")
        public <T> T body(BodyExtractor<T, ? super org.springframework.http.client.reactive.ClientHttpResponse> extractor) {
            try {
                T body = super.body(extractor);
                if (body instanceof Mono<?> mono) {
                    return (T) map(mono);
                }
                if (body instanceof Flux<?> flux) {
                    return (T) map(flux);
                }
                return body;
            } catch (ExternalServiceException exception) {
                throw exception;
            } catch (Throwable failure) {
                throw mapFailure(failure);
            }
        }

        private <T> Mono<T> map(Mono<T> body) {
            return body.onErrorMap(this::shouldMap, this::mapFailure);
        }

        private <T> Flux<T> map(Flux<T> body) {
            return body.onErrorMap(this::shouldMap, this::mapFailure);
        }

        private boolean shouldMap(Throwable failure) {
            return !(failure instanceof ExternalServiceException);
        }

        private ExternalServiceException mapFailure(Throwable failure) {
            return errorMapper.forFailure(failure, context);
        }
    }
}

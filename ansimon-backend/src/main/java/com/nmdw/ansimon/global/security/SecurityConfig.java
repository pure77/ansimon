package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.config.CorsConfig;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AnonymousAuthenticationFilter;
import org.springframework.web.cors.CorsConfigurationSource;
import tools.jackson.databind.json.JsonMapper;

/**
 * 외부 공개 API와 서버 간 내부 API에 서로 다른 보안 정책을 적용하는 두 개의 필터 체인을 정의합니다.
 * {@code /internal/**} 체인이 먼저 매칭되어 Bearer 키 인증을 강제하고 CORS를 꺼 브라우저 호출을 막으며,
 * 나머지 요청은 공개 체인이 받아 {@code /api/**}에만 관리자 프론트엔드 CORS를 허용합니다.
 */
@Configuration
@EnableWebSecurity
@EnableConfigurationProperties(InternalApiProperties.class)
@Import(CorsConfig.class)
public class SecurityConfig {

    @Bean
    @Order(1)
    public SecurityFilterChain internalApiSecurityFilterChain(
            HttpSecurity http, InternalApiProperties internalApiProperties, JsonMapper jsonMapper) throws Exception {
        return statelessApi(http)
                .securityMatcher("/internal/**")
                .cors(AbstractHttpConfigurer::disable)
                .addFilterBefore(new InternalApiKeyFilter(internalApiProperties), AnonymousAuthenticationFilter.class)
                .exceptionHandling(exceptions -> exceptions
                        .authenticationEntryPoint(new JsonAuthenticationEntryPoint(jsonMapper)))
                .authorizeHttpRequests(authorize -> authorize.anyRequest().hasRole("INTERNAL"))
                .build();
    }

    @Bean
    @Order(2)
    public SecurityFilterChain publicApiSecurityFilterChain(
            HttpSecurity http, CorsConfigurationSource corsConfigurationSource) throws Exception {
        return statelessApi(http)
                .cors(cors -> cors.configurationSource(corsConfigurationSource))
                .authorizeHttpRequests(authorize -> authorize.anyRequest().permitAll())
                .build();
    }

    private static HttpSecurity statelessApi(HttpSecurity http) throws Exception {
        return http
                .csrf(AbstractHttpConfigurer::disable)
                .httpBasic(AbstractHttpConfigurer::disable)
                .formLogin(AbstractHttpConfigurer::disable)
                .logout(AbstractHttpConfigurer::disable)
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS));
    }
}

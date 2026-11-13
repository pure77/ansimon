package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.config.CorsConfig;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AnonymousAuthenticationFilter;
import org.springframework.web.cors.CorsConfigurationSource;
import tools.jackson.databind.json.JsonMapper;

/**
 * 서버 간 내부 API, 관리자 API, 그 밖의 공개 경로에 서로 다른 보안 정책을 적용하는 세 개의 필터 체인을 정의합니다.
 * {@code /internal/**}는 Bearer 내부 키, {@code /api/**}는 관리자 JWT를 요구하며 관리자 프론트엔드 CORS는 이 체인에만 허용합니다.
 * 로그인과 CORS preflight만 토큰 없이 통과하고, 나머지 경로(헬스체크·API 문서)는 공개 체인이 받습니다.
 */
@Configuration
@EnableWebSecurity
@EnableConfigurationProperties(InternalApiProperties.class)
@Import({CorsConfig.class, JwtConfig.class})
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
    public SecurityFilterChain adminApiSecurityFilterChain(
            HttpSecurity http, CorsConfigurationSource corsConfigurationSource, JsonMapper jsonMapper) throws Exception {
        JsonAuthenticationEntryPoint entryPoint = new JsonAuthenticationEntryPoint(jsonMapper);
        return statelessApi(http)
                .securityMatcher("/api/**")
                .cors(cors -> cors.configurationSource(corsConfigurationSource))
                .oauth2ResourceServer(resourceServer -> resourceServer
                        .jwt(Customizer.withDefaults())
                        .authenticationEntryPoint(entryPoint))
                .exceptionHandling(exceptions -> exceptions.authenticationEntryPoint(entryPoint))
                .authorizeHttpRequests(authorize -> authorize
                        .requestMatchers(HttpMethod.OPTIONS, "/api/**").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/v1/auth/login").permitAll()
                        .anyRequest().hasAuthority("SCOPE_admin"))
                .build();
    }

    @Bean
    @Order(3)
    public SecurityFilterChain publicSecurityFilterChain(HttpSecurity http) throws Exception {
        return statelessApi(http)
                .cors(AbstractHttpConfigurer::disable)
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

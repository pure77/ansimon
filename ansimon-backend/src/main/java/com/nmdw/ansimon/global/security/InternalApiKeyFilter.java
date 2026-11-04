package com.nmdw.ansimon.global.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;

/**
 * {@code /internal/**} 요청의 {@code Authorization: Bearer} 키를 설정된 키 목록과 비교해 내부 서비스로 인증합니다.
 * 비교는 {@link MessageDigest#isEqual}로 하고 모든 키를 끝까지 비교해, 응답 시간으로 키를 추측할 수 없게 합니다.
 * 키가 맞지 않으면 아무것도 설정하지 않고 넘기며, 거절 응답은 체인의 인가 단계와 {@link JsonAuthenticationEntryPoint}가 만듭니다.
 * 빈으로 등록하면 서블릿 필터로 모든 경로에 자동 적용되므로 {@link SecurityConfig}에서만 생성합니다.
 */
public class InternalApiKeyFilter extends OncePerRequestFilter {

    private static final String BEARER_PREFIX = "Bearer ";
    private static final String PRINCIPAL = "internal-service";

    private final List<byte[]> acceptedKeys;

    public InternalApiKeyFilter(InternalApiProperties properties) {
        this.acceptedKeys = properties.apiKeys().stream()
                .map(key -> key.getBytes(StandardCharsets.UTF_8))
                .toList();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header != null && header.startsWith(BEARER_PREFIX)
                && matchesAnyKey(header.substring(BEARER_PREFIX.length()).trim())) {
            SecurityContext context = SecurityContextHolder.createEmptyContext();
            context.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(
                    PRINCIPAL, null, List.of(new SimpleGrantedAuthority("ROLE_INTERNAL"))));
            SecurityContextHolder.setContext(context);
        }
        chain.doFilter(request, response);
    }

    private boolean matchesAnyKey(String presented) {
        byte[] candidate = presented.getBytes(StandardCharsets.UTF_8);
        boolean matched = false;
        for (byte[] key : acceptedKeys) {
            matched |= MessageDigest.isEqual(key, candidate);
        }
        return matched;
    }
}

package com.nmdw.ansimon.global.response;

import org.springframework.data.domain.Page;

import java.util.List;

/**
 * 목록 API가 {@link ApiResponse}의 {@code data}에 담는 공통 페이지네이션 형태입니다.
 * Spring {@link Page}의 내부 필드(pageable, sort 등)를 그대로 노출하지 않고 클라이언트가 필요로 하는 값만 전달합니다.
 */
public record PageResponse<T>(
        List<T> content,
        int page,
        int size,
        long totalElements,
        int totalPages
) {

    public static <T> PageResponse<T> from(Page<T> page) {
        return new PageResponse<>(
                page.getContent(),
                page.getNumber(),
                page.getSize(),
                page.getTotalElements(),
                page.getTotalPages()
        );
    }
}

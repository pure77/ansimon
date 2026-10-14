package com.nmdw.ansimon.contact.api;

import com.nmdw.ansimon.contact.application.CallObservationService;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.dto.CallObservationListResponse;
import com.nmdw.ansimon.contact.dto.CallObservationResponse;
import com.nmdw.ansimon.contact.dto.CallObservationUpdateRequest;
import com.nmdw.ansimon.global.response.ApiResponse;
import com.nmdw.ansimon.global.response.PageResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springdoc.core.annotations.ParameterObject;
import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PageableDefault;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;

/**
 * 저장된 통화 결과를 담당자가 교정하거나 삭제하는 REST 컨트롤러입니다.
 * 요청 검증과 HTTP 응답 변환만 담당하고 실제 교정·삭제는 {@link CallObservationService}에 위임합니다.
 */
@Tag(name = "통화 결과", description = "외부 서버가 저장한 통화 결과를 담당자가 교정하거나 삭제합니다.")
@RestController
@RequestMapping("/api/v1/contact/observations")
public class CallObservationController {

    private final CallObservationService callObservationService;

    public CallObservationController(CallObservationService callObservationService) {
        this.callObservationService = callObservationService;
    }

    @Operation(summary = "통화 결과 목록 조회",
            description = "저장된 통화 결과를 최신순으로 조회합니다. "
                    + "elderlyId를 주면 해당 어르신만, date를 주면 그 날짜(Asia/Seoul)에 끝난 통화만 봅니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "조회 조건 또는 페이지 요청값 오류")
    })
    @GetMapping
    public ApiResponse<PageResponse<CallObservationListResponse>> list(
            @Parameter(description = "어르신 식별자", example = "10", in = ParameterIn.QUERY)
            @RequestParam(required = false) Long elderlyId,
            @Parameter(description = "통화 결과 상태", example = "ANSWERED", in = ParameterIn.QUERY)
            @RequestParam(required = false) ContactStatus status,
            @Parameter(description = "통화 종료 날짜(Asia/Seoul)", example = "2026-08-19", in = ParameterIn.QUERY)
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @ParameterObject
            @PageableDefault(size = 20) Pageable pageable) {
        return ApiResponse.success(callObservationService.search(elderlyId, status, date, pageable));
    }

    @Operation(summary = "통화 결과 교정",
            description = "LLM이 잘못 판단한 요약과 판정 항목을 담당자가 바로잡습니다. 전달한 항목만 수정되고 나머지는 유지됩니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "교정 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "통화 결과를 찾을 수 없음")
    })
    @PatchMapping("/{id}")
    public ApiResponse<CallObservationResponse> update(
            @Parameter(description = "통화 결과 식별자", example = "5", required = true)
            @PathVariable Long id,
            @Valid @RequestBody CallObservationUpdateRequest request) {
        return ApiResponse.success(callObservationService.update(id, request));
    }

    @Operation(summary = "통화 결과 삭제",
            description = "잘못 저장된 통화 결과를 삭제합니다. 전화 작업은 남으므로 같은 통화에 대한 결과를 다시 저장할 수 있습니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "204", description = "삭제 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "통화 결과를 찾을 수 없음")
    })
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(
            @Parameter(description = "통화 결과 식별자", example = "5", required = true)
            @PathVariable Long id) {
        callObservationService.delete(id);
        return ResponseEntity.noContent().build();
    }
}

package com.nmdw.ansimon.elderly.api;

import com.nmdw.ansimon.elderly.application.ElderlyService;
import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.dto.ElderlyRegisterRequest;
import com.nmdw.ansimon.elderly.dto.ElderlyResponse;
import com.nmdw.ansimon.elderly.dto.ElderlyUpdateRequest;
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
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 관리 대상 노인의 등록, 조건별 목록 조회, 단건 조회, 부분 수정을 제공하는 REST 컨트롤러입니다.
 * 요청 검증과 HTTP 응답 변환만 담당하고 실제 등록·조회·변경 흐름은 {@link ElderlyService}에 위임합니다.
 */
@Tag(name = "노인 관리", description = "폭염 취약 노인의 프로필, 주소, 자동전화 동의 상태를 관리합니다.")
@RestController
@RequestMapping("/api/v1/elderly")
public class ElderlyController {

    private final ElderlyService elderlyService;

    public ElderlyController(ElderlyService elderlyService) {
        this.elderlyService = elderlyService;
    }

    @Operation(summary = "노인 등록", description = "주소를 좌표와 행정구역 코드로 변환한 뒤 관리 대상 노인을 등록합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "201", description = "등록 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "요청값 검증 실패"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "502", description = "지오코딩 외부 서비스 오류"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "504", description = "지오코딩 외부 서비스 시간 초과")
    })
    @PostMapping
    public ResponseEntity<ApiResponse<ElderlyResponse>> register(@Valid @RequestBody ElderlyRegisterRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(elderlyService.register(request)));
    }

    @Operation(summary = "노인 목록 조회", description = "행정구역 코드와 자동전화 동의 상태로 필터링한 노인 목록을 페이지 단위로 조회합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "조회 조건 또는 페이지 요청값 오류")
    })
    @GetMapping
    public ApiResponse<PageResponse<ElderlyResponse>> list(
            @Parameter(description = "행정구역 코드", example = "11110", in = ParameterIn.QUERY)
            @RequestParam(required = false) String regionCode,
            @Parameter(description = "자동전화 동의 상태", example = "consented", in = ParameterIn.QUERY)
            @RequestParam(required = false) ConsentStatus consentStatus,
            @ParameterObject
            @PageableDefault(size = 20, sort = "id") Pageable pageable) {
        return ApiResponse.success(elderlyService.list(regionCode, consentStatus, pageable));
    }

    @Operation(summary = "노인 단건 조회", description = "식별자로 관리 대상 노인의 상세 프로필을 조회합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "노인 프로필을 찾을 수 없음")
    })
    @GetMapping("/{id}")
    public ApiResponse<ElderlyResponse> getById(
            @Parameter(description = "노인 프로필 식별자", example = "1", required = true)
            @PathVariable Long id) {
        return ApiResponse.success(elderlyService.getById(id));
    }

    @Operation(summary = "노인 정보 수정", description = "이름, 전화번호, 주소, 자동전화 동의 상태 중 전달된 값만 수정합니다. 주소 변경 시 좌표와 행정구역 코드도 갱신합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "수정 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "요청값 검증 실패"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "노인 프로필을 찾을 수 없음"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "502", description = "지오코딩 외부 서비스 오류"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "504", description = "지오코딩 외부 서비스 시간 초과")
    })
    @PatchMapping("/{id}")
    public ApiResponse<ElderlyResponse> update(
            @Parameter(description = "노인 프로필 식별자", example = "1", required = true)
            @PathVariable Long id,
            @Valid @RequestBody ElderlyUpdateRequest request) {
        return ApiResponse.success(elderlyService.update(id, request));
    }

    @Operation(summary = "노인 삭제",
            description = "잘못 등록한 대상자를 삭제합니다. 안내계획·전화 작업·지원 업무 이력이 남아 있으면 삭제할 수 없으며, "
                    + "이 경우 삭제 대신 동의 철회로 관리합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "204", description = "삭제 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "노인 프로필을 찾을 수 없음"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "409", description = "안내계획·전화 이력이 있어 삭제할 수 없음")
    })
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(
            @Parameter(description = "노인 프로필 식별자", example = "1", required = true)
            @PathVariable Long id) {
        elderlyService.delete(id);
        return ResponseEntity.noContent().build();
    }
}

package com.nmdw.ansimon.contact.api;

import com.nmdw.ansimon.contact.application.ContactService;
import com.nmdw.ansimon.contact.dto.CallOutcomeRequest;
import com.nmdw.ansimon.contact.dto.CallOutcomeResponse;
import com.nmdw.ansimon.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 외부 LLM/RAG 서버가 대응계획 생성과 전화를 마친 뒤 보내는 최종 결과를 받는 내부 콜백 컨트롤러입니다.
 * 요청 검증과 HTTP 응답 변환만 담당하고 저장 흐름은 {@link ContactService}에 위임합니다.
 */
@Tag(name = "예방 전화 결과 (내부)", description = "외부 LLM/RAG 서버가 생성한 대응계획과 통화 결과를 한 번에 저장합니다.")
@RestController
@RequestMapping("/internal/v1/contact")
public class ContactController {

    private final ContactService contactService;

    public ContactController(ContactService contactService) {
        this.contactService = contactService;
    }

    @Operation(summary = "대응계획 + 통화 결과 저장",
            description = "외부 서버가 대응계획을 만들고 전화까지 마친 뒤 결과를 한 번에 전송합니다. "
                    + "안내계획, 전화 작업, 통화 결과가 함께 생성되며 `externalCallId`로 중복 전송을 막습니다. "
                    + "미응답이면 요약 없이 결과만 기록합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "201", description = "저장 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "요청값 검증 실패 또는 응답 통화인데 요약·판정값 누락"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "노인 또는 위험도 스냅샷을 찾을 수 없음"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "409", description = "이미 저장된 externalCallId")
    })
    @PostMapping("/results")
    public ResponseEntity<ApiResponse<CallOutcomeResponse>> registerCallOutcome(
            @Valid @RequestBody CallOutcomeRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(contactService.registerCallOutcome(request)));
    }
}

package com.nmdw.ansimon.elderly.dto;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;

/**
 * 기존 노인 프로필에서 전달된 항목만 변경하기 위한 부분 수정 요청입니다.
 * 주소가 전달되면 서비스가 좌표와 행정구역 코드까지 다시 계산합니다.
 */
@Schema(description = "노인 정보 부분 수정 요청")
public record ElderlyUpdateRequest(
        @Schema(description = "변경할 표시 이름", example = "김안심")
        @Size(max = 100) String displayName,
        @Schema(description = "변경할 전화번호", example = "010-1234-5678")
        @Size(max = 128) String phone,
        @Schema(description = "변경할 거주지 전체 주소", example = "서울특별시 종로구 세종대로 1")
        @Size(max = 255) String address,
        @Schema(description = "변경할 자동전화 동의 상태", example = "withdrawn")
        ConsentStatus consentStatus,
        @Schema(description = "변경할 생년월일", example = "1950-03-01")
        LocalDate birthDate,
        @Schema(description = "변경할 기저질환/건강상태 메모", example = "고혈압, 당뇨")
        @Size(max = 500) String healthNote
) {
}

package com.nmdw.ansimon.elderly.dto;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;

/**
 * 노인 프로필을 새로 등록할 때 클라이언트가 전달하는 요청입니다.
 * 주소의 좌표와 행정구역 코드는 서버가 지오코딩하므로 요청에 포함하지 않습니다.
 */
@Schema(description = "노인 등록 요청")
public record ElderlyRegisterRequest(
        @Schema(description = "화면에 표시할 이름", example = "김안심")
        @NotBlank @Size(max = 100) String displayName,
        @Schema(description = "연락 가능한 전화번호", example = "010-1234-5678")
        @NotBlank @Size(max = 128) String phone,
        @Schema(description = "거주지 전체 주소", example = "서울특별시 종로구 세종대로 1")
        @NotBlank @Size(max = 255) String address,
        @Schema(description = "자동전화 동의 상태", example = "consented")
        @NotNull ConsentStatus consentStatus,
        @Schema(description = "생년월일", example = "1950-03-01")
        LocalDate birthDate,
        @Schema(description = "기저질환/건강상태 메모", example = "고혈압, 당뇨")
        @Size(max = 500) String healthNote
) {
}

package com.nmdw.ansimon.global.response;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;

class ApiResponseTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void successPlacesPayloadInDataAndLeavesErrorEmpty() {
        ApiResponse<String> response = ApiResponse.success("guidance plan");

        assertThat(response.success()).isTrue();
        assertThat(response.data()).isEqualTo("guidance plan");
        assertThat(response.error()).isNull();
    }

    @Test
    void failurePlacesCompleteStructuredErrorInErrorAndLeavesDataEmpty() throws Exception {
        ErrorResponse error = new ErrorResponse(
                "GUIDANCE_NOT_FOUND",
                "Guidance plan was not found.",
                Map.of("guidanceId", "guidance-123")
        );

        ApiResponse<Void> response = ApiResponse.failure(error);

        assertThat(response.success()).isFalse();
        assertThat(response.data()).isNull();
        assertThat(response.error()).isEqualTo(error);
        assertThat(objectMapper.writeValueAsString(response)).isEqualTo(
                "{\"success\":false,\"data\":null,\"error\":{\"code\":\"GUIDANCE_NOT_FOUND\",\"message\":\"Guidance plan was not found.\",\"details\":{\"guidanceId\":\"guidance-123\"}}}"
        );
    }

    @Test
    void failureRejectsNullError() {
        assertThatNullPointerException()
                .isThrownBy(() -> ApiResponse.failure(null))
                .withMessage("error must not be null");
    }
}

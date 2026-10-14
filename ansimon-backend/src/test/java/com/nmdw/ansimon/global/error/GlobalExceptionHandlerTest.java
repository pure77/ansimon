package com.nmdw.ansimon.global.error;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Pattern;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpMethod;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = GlobalExceptionHandlerTest.TestController.class)
@Import(GlobalExceptionHandlerTest.TestController.class)
class GlobalExceptionHandlerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void mapsBusinessExceptionToItsConfiguredErrorResponse() throws Exception {
        mockMvc.perform(get("/test/business"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data").value(nullValue()))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_CONFLICT"))
                .andExpect(jsonPath("$.error.message").value("The request conflicts with the current state."));
    }

    @Test
    void mapsValidationFailureWithoutExposingTheRejectedValue() throws Exception {
        mockMvc.perform(post("/test/validated").contentType("application/json").content("{\"name\":\"private-value\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data").value(nullValue()))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_VALIDATION_ERROR"))
                .andExpect(jsonPath("$.error.details.fields[0].field").value("name"))
                .andExpect(jsonPath("$.error.details.fields[0].message").value("Invalid value."))
                .andExpect(jsonPath("$..*[?(@ == 'private-value')]").doesNotExist());
    }

    @Test
    void mapsUnreadableJsonToGenericMalformedRequestResponse() throws Exception {
        mockMvc.perform(post("/test/validated").contentType("application/json").content("{\"name\":"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data").value(nullValue()))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_MALFORMED_REQUEST"))
                .andExpect(jsonPath("$.error.message").value("The request could not be read."));
    }

    @Test
    void mapsMissingRequiredRequestParameterToValidationError() throws Exception {
        mockMvc.perform(get("/test/required"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("GLOBAL_VALIDATION_ERROR"));
    }

    @Test
    void mapsUnsupportedMediaTypeWithoutExposingRequestBody() throws Exception {
        mockMvc.perform(post("/test/validated").contentType("text/plain").content("private-value"))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(jsonPath("$.error.code").value("GLOBAL_UNSUPPORTED_MEDIA_TYPE"))
                .andExpect(jsonPath("$..*[?(@ == 'private-value')]").doesNotExist());
    }

    @Test
    void mapsUnsupportedMethodToMethodNotAllowed() throws Exception {
        mockMvc.perform(put("/test/validated").contentType("application/json").content("{\"name\":\"PRIVATE\"}"))
                .andExpect(status().isMethodNotAllowed())
                .andExpect(jsonPath("$.error.code").value("GLOBAL_METHOD_NOT_ALLOWED"))
                .andExpect(jsonPath("$..*[?(@ == 'PRIVATE')]").doesNotExist());
    }

    @Test
    void mapsMissingResourceToNotFoundResponse() throws Exception {
        mockMvc.perform(get("/test/missing"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data").value(nullValue()))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_RESOURCE_NOT_FOUND"));
    }

    @Test
    void mapsUnexpectedExceptionWithoutExposingItsMessage() throws Exception {
        mockMvc.perform(get("/test/unexpected"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data").value(nullValue()))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_INTERNAL_ERROR"))
                .andExpect(jsonPath("$.error.message").value("An unexpected error occurred."))
                .andExpect(jsonPath("$..*[?(@ == 'sensitive internal detail')]").doesNotExist());
    }

    @RestController
    @RequestMapping("/test")
    static class TestController {
        @GetMapping("/business") void business() { throw new BusinessException(ErrorCode.CONFLICT); }
        @PostMapping("/validated") void validated(@Valid @RequestBody TestRequest request) { }
        @GetMapping("/required") String required(@RequestParam String value) { return value; }
        @GetMapping("/missing") void missing() throws NoResourceFoundException { throw new NoResourceFoundException(HttpMethod.GET, "/test/missing", ""); }
        @GetMapping("/unexpected") void unexpected() { throw new IllegalStateException("sensitive internal detail"); }
    }

    record TestRequest(@Pattern(regexp = "^[A-Z]+$") String name) { }
}

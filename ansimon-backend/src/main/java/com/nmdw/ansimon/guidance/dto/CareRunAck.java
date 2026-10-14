package com.nmdw.ansimon.guidance.dto;

import java.util.Map;

/** 커넥션의 완료 응답에서 호출 확인에 필요한 값만 추출합니다. */
public record CareRunAck(String externalCallId, Boolean answered) {

    public static CareRunAck from(Map<String, Object> body) {
        Map<?, ?> data = nestedMap(body, "data");
        Map<?, ?> result = nestedMap(data, "result");
        Map<?, ?> call = nestedMap(result, "call");
        String externalCallId = result == null ? null : asString(result.get("externalCallId"));
        Boolean answered = call == null ? null : asBoolean(call.get("answered"));
        return new CareRunAck(externalCallId, answered);
    }

    private static Map<?, ?> nestedMap(Map<?, ?> source, String key) {
        Object value = source == null ? null : source.get(key);
        return value instanceof Map<?, ?> map ? map : null;
    }

    private static String asString(Object value) {
        return value instanceof String string ? string : null;
    }

    private static Boolean asBoolean(Object value) {
        return value instanceof Boolean bool ? bool : null;
    }
}

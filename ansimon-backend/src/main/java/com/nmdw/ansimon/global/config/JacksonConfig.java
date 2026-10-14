package com.nmdw.ansimon.global.config;

import org.springframework.boot.jackson.autoconfigure.JsonMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.core.JsonGenerator;
import tools.jackson.core.JsonParser;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.DeserializationContext;
import tools.jackson.databind.SerializationContext;
import tools.jackson.databind.ValueDeserializer;
import tools.jackson.databind.ValueSerializer;
import tools.jackson.databind.module.SimpleModule;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

/**
 * API에서 {@link Instant}를 일관된 서울 시간대 ISO-8601 오프셋 문자열로 직렬화하고 역직렬화하도록 Jackson을 구성합니다.
 * 저장과 도메인 로직은 UTC 기준 {@code Instant}를 유지하되, 클라이언트에는 서비스 기준 시간대인 Asia/Seoul을 명시해 전달합니다.
 * 등록한 모듈은 애플리케이션의 JSON 매퍼 전반에 적용되어 시간 표현 정책을 중앙화합니다.
 */
@Configuration
public class JacksonConfig {

    private static final ZoneId ASIA_SEOUL = ZoneId.of("Asia/Seoul");

    @Bean
    public JsonMapperBuilderCustomizer asiaSeoulInstantJsonMapperCustomizer() {
        return builder -> builder.addModule(instantModule());
    }

    private SimpleModule instantModule() {
        SimpleModule instantModule = new SimpleModule();
        instantModule.addSerializer(Instant.class, new AsiaSeoulInstantSerializer());
        instantModule.addDeserializer(Instant.class, new InstantDeserializer());
        return instantModule;
    }

    /**
     * UTC {@link Instant}를 Asia/Seoul 오프셋이 포함된 API 문자열로 변환하는 Jackson 전용 직렬화기입니다.
     * {@link JacksonConfig}가 만든 모듈 내부에서만 사용되어, 시간대 표시 정책이 개별 응답 DTO로 흩어지지 않게 합니다.
     */
    private static final class AsiaSeoulInstantSerializer extends ValueSerializer<Instant> {

        @Override
        public void serialize(Instant value, JsonGenerator generator, SerializationContext context) throws JacksonException {
            generator.writeString(DateTimeFormatter.ISO_OFFSET_DATE_TIME.format(value.atZone(ASIA_SEOUL)));
        }
    }

    /**
     * API 요청의 ISO-8601 오프셋 문자열을 UTC {@link Instant}로 복원하는 Jackson 전용 역직렬화기입니다.
     * 입력 문자열의 오프셋을 보존해 해석한 뒤 공통 시간 표현인 {@code Instant}로 변환합니다.
     */
    private static final class InstantDeserializer extends ValueDeserializer<Instant> {

        @Override
        public Instant deserialize(JsonParser parser, DeserializationContext context) throws JacksonException {
            return OffsetDateTime.parse(parser.getValueAsString(), DateTimeFormatter.ISO_OFFSET_DATE_TIME).toInstant();
        }
    }
}

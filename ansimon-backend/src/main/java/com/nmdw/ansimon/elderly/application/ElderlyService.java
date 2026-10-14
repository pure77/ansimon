package com.nmdw.ansimon.elderly.application;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.dto.ElderlyRegisterRequest;
import com.nmdw.ansimon.elderly.dto.ElderlyResponse;
import com.nmdw.ansimon.elderly.dto.ElderlyUpdateRequest;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.response.PageResponse;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

/**
 * 노인 프로필 등록, 조회, 수정 유스케이스를 조율하는 애플리케이션 서비스입니다.
 * 주소가 등록·변경되면 {@link GeocodingClient}로 좌표와 행정구역 코드를 함께 구하고,
 * 영속화된 도메인 모델을 API 응답 DTO로 변환합니다.
 */
@Service
@Transactional
public class ElderlyService {

    private final ElderlyProfileRepository repository;
    private final GeocodingClient geocodingClient;

    public ElderlyService(ElderlyProfileRepository repository, GeocodingClient geocodingClient) {
        this.repository = repository;
        this.geocodingClient = geocodingClient;
    }

    public ElderlyResponse register(ElderlyRegisterRequest request) {
        GeocodingResult location = geocodingClient.geocode(request.address());
        ElderlyProfile profile = ElderlyProfile.builder()
                .displayName(request.displayName()).phone(request.phone()).address(request.address())
                .latitude(location.latitude()).longitude(location.longitude()).regionCode(location.regionCode())
                .consentStatus(request.consentStatus())
                .birthDate(request.birthDate()).healthNote(request.healthNote()).build();
        return ElderlyResponse.from(repository.save(profile));
    }

    @Transactional(readOnly = true)
    public PageResponse<ElderlyResponse> list(String regionCode, ConsentStatus consentStatus, Pageable pageable) {
        return PageResponse.from(repository.search(regionCode, consentStatus, pageable).map(ElderlyResponse::from));
    }

    @Transactional(readOnly = true)
    public ElderlyResponse getById(Long id) {
        return ElderlyResponse.from(findById(id));
    }

    public ElderlyResponse update(Long id, ElderlyUpdateRequest request) {
        ElderlyProfile profile = findById(id);
        if (StringUtils.hasText(request.displayName()) || StringUtils.hasText(request.phone())) {
            profile.updateProfile(StringUtils.hasText(request.displayName()) ? request.displayName() : profile.getDisplayName(),
                    StringUtils.hasText(request.phone()) ? request.phone() : profile.getPhone());
        }
        if (StringUtils.hasText(request.address())) {
            GeocodingResult location = geocodingClient.geocode(request.address());
            profile.updateAddress(request.address(), location.latitude(), location.longitude(), location.regionCode());
        }
        if (request.consentStatus() != null) {
            profile.updateConsentStatus(request.consentStatus());
        }
        if (request.birthDate() != null || StringUtils.hasText(request.healthNote())) {
            profile.updateHealthInfo(
                    request.birthDate() != null ? request.birthDate() : profile.getBirthDate(),
                    StringUtils.hasText(request.healthNote()) ? request.healthNote() : profile.getHealthNote());
        }
        return ElderlyResponse.from(profile);
    }

    /**
     * 잘못 등록한 대상자를 삭제합니다.
     * 안내계획·전화 작업·지원 업무가 이미 남아 있으면 돌봄 이력이 끊기므로 외래키 제약이 삭제를 막고, 이를 충돌로 변환합니다.
     * 이력이 있는 대상자는 삭제 대신 동의 철회(`WITHDRAWN`)로 관리합니다.
     */
    public void delete(Long id) {
        repository.delete(findById(id));
        try {
            repository.flush();
        } catch (DataIntegrityViolationException exception) {
            throw new BusinessException(ErrorCode.CONFLICT, exception);
        }
    }

    private ElderlyProfile findById(Long id) {
        return repository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));
    }
}

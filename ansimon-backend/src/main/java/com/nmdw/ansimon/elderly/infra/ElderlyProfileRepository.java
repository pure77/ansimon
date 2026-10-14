package com.nmdw.ansimon.elderly.infra;

import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * {@link ElderlyProfile}의 영속화와 조건 검색을 담당하는 Spring Data JPA 저장소입니다.
 * 행정구역 코드와 자동전화 동의 상태를 선택적으로 조합한 페이지 검색을 제공합니다.
 */
public interface ElderlyProfileRepository extends JpaRepository<ElderlyProfile, Long> {

    @Query("SELECT e FROM ElderlyProfile e WHERE (:regionCode IS NULL OR e.regionCode = :regionCode) "
            + "AND (:consentStatus IS NULL OR e.consentStatus = :consentStatus)")
    Page<ElderlyProfile> search(@Param("regionCode") String regionCode,
                                @Param("consentStatus") ConsentStatus consentStatus,
                                Pageable pageable);
}

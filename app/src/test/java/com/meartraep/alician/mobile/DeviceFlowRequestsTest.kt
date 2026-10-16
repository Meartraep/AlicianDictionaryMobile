package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.DeviceFlowRequests
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The device flow talks to two different endpoints, and mixing them up makes GitHub
 * answer "incorrect_client_credentials" -- which reads like a wrong Client ID.
 * These tests pin the endpoint and body of each call.
 */
class DeviceFlowRequestsTest {
    private val clientId = "Iv23liFAV6KmO0n2x8hW"

    @Test
    fun deviceCodeIsRequestedFromTheDeviceEndpoint() {
        val request = DeviceFlowRequests.deviceCode(clientId)
        assertEquals("https://github.com/login/device/code", request.url)
        assertEquals("client_id=" + clientId, request.body)
    }

    @Test
    fun pollingUsesTheTokenEndpointWithTheDeviceGrant() {
        val request = DeviceFlowRequests.poll(clientId, "device-code-123")
        assertEquals("https://github.com/login/oauth/access_token", request.url)
        assertTrue(request.body, request.body.startsWith("client_id=" + clientId))
        assertTrue(request.body, request.body.contains("device_code=device-code-123"))
        assertTrue(
            request.body,
            request.body.contains("grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code"),
        )
    }

    @Test
    fun refreshUsesTheRefreshGrant() {
        val request = DeviceFlowRequests.refresh(clientId, "refresh-123")
        assertEquals("https://github.com/login/oauth/access_token", request.url)
        assertTrue(request.body, request.body.contains("grant_type=refresh_token"))
        assertTrue(request.body, request.body.contains("refresh_token=refresh-123"))
    }

    @Test
    fun theDeviceCodeAndTokenEndpointsAreDifferent() {
        assertNotEquals(DeviceFlowRequests.DEVICE_CODE_URL, DeviceFlowRequests.TOKEN_URL)
        assertNotEquals(
            DeviceFlowRequests.deviceCode(clientId).url,
            DeviceFlowRequests.poll(clientId, "device-code-123").url,
        )
    }
}

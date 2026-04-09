package com.however.microservices.adservice;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.lang.reflect.Method;
import org.junit.jupiter.api.Test;

class AdServiceClientTest {

  @Test
  void getPortOrDefaultFromArgsReturnsDefaultWhenInvalid() throws Exception {
    Method method = AdServiceClient.class.getDeclaredMethod("getPortOrDefaultFromArgs", String[].class);
    method.setAccessible(true);
    int port = (int) method.invoke(null, (Object) new String[] {"camera", "localhost", "bad-port"});
    assertEquals(9555, port);
  }

  @Test
  void getPortOrDefaultFromArgsParsesValidPort() throws Exception {
    Method method = AdServiceClient.class.getDeclaredMethod("getPortOrDefaultFromArgs", String[].class);
    method.setAccessible(true);
    int port = (int) method.invoke(null, (Object) new String[] {"camera", "localhost", "9666"});
    assertEquals(9666, port);
  }
}

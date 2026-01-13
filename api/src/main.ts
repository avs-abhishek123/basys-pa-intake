import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    logger: ['error', 'warn', 'log'],
  });

  // Enable validation
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  // Enable CORS
  app.enableCors();

  const port = process.env.PORT || 3000;
  await app.listen(port);

  console.log(`✓ API Server listening on port ${port}`);
  console.log(
    JSON.stringify({
      type: 'server_start',
      port,
      timestamp: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
    }),
  );
}

bootstrap();

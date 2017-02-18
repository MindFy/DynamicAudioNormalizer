##################################################################################
# Dynamic Audio Normalizer - Python Wrapper
# Copyright (c) 2014-2017 LoRd_MuldeR <mulder2@gmx.de>. Some rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# http://opensource.org/licenses/MIT
##################################################################################

#import stdlib modules
import sys
import os
import array
import struct
import wave

#import the "C" module
import DynamicAudioNormalizerAPI 


#----------------------------------------------------------------------
# DynamicAudioNormalizer
#----------------------------------------------------------------------

class DynamicAudioNormalizer:
	"""Wrapper class around the DynamicAudioNormalizerAPI library"""
	
	def __str__(self):
		versionInfo = self.getVersion()
		buildStr = "built: {} {}, compiler: {}, arch: {}, {}".format(*versionInfo[1])
		configStr = "channels={}, samplingRate={}, frameLen={}, filterSize={}".format(*self.getConfig())
		return "DynamicAudioNormalizer v{}.{}-{} [{}][{}]]".format(*versionInfo[0], buildStr, configStr)
	
	def __init__(self,channels,samplerate):
		self._channels = channels
		self._samplerate = samplerate
		self._instance = None
	
	def __enter__(self):
		self._instance = DynamicAudioNormalizerAPI.create(self._channels, self._samplerate)
		return self
	
	def __exit__(self, type, value, traceback):
		if not self._instance:
			raise RuntimeError("Instance not initialized!")
		DynamicAudioNormalizerAPI.destroy(self._instance)
		self._instance = None
	
	def __del__(self):
		if self._instance:
			print("RESOURCE LEAK: DynamicAudioNormalizer object was not de-initialized properly!", file=sys.stderr)
	
	def getConfig(self):
		if not self._instance:
			raise RuntimeError("Instance not initialized!")
		return DynamicAudioNormalizerAPI.getConfig(self._instance)
	
	def processInplace(self, samplesInOut, count):
		if not self._instance:
			raise RuntimeError("Instance not initialized!")
		return DynamicAudioNormalizerAPI.processInplace(self._instance, samplesInOut, count)
	
	@staticmethod
	def getVersion():
		return DynamicAudioNormalizerAPI.getVersion()


#----------------------------------------------------------------------
# Wave Audio Reader/Writer
#----------------------------------------------------------------------

class _WaveFileBase:
	"""Base class for Wave file sample processing"""
	
	def __init__(self):
		self._samples = None
	
	def _unpack_samples(self, samples, buffers, channels, sampwidth):
		cidx, sidx = 0, 0
		type = self._get_sample_type(sampwidth)
		for sample in struct.iter_unpack(type[0], samples):
			buffers[cidx][sidx] = float(sample[0]) / float(type[1])
			cidx += 1
			if cidx >= channels:
				cidx, sidx = 0, sidx + 1
		return sidx
	
	def _repack_samples(self, buffers, channels, sampwidth, length):
		byte_count = channels * length * sampwidth
		type = self._get_sample_type(sampwidth)
		if (not self._samples) or (len(self._samples) != byte_count):
			self._samples = bytearray(byte_count)
		offset = 0
		for sidx in range(0, length):
			for cidx in range(0, channels):
				if type[1] > 1.4142:
					value = int(round(buffers[cidx][sidx] * type[1]))
				else:
					value = buffers[cidx][sidx]
				struct.pack_into(type[0], self._samples, offset, value)
				offset += sampwidth
		return self._samples
	
	def _minimum_buff_length(self, buffers):
		result = sys.maxsize
		for b in buffers:
			result = min(result, len(b))
		if result < 1:
			raise ValueError("Buffer length is zero!")
		return result
	
	def _get_sample_type(self, sampwidth):
		if sampwidth == 2:
			return ('<h', 0x7FFF)
		elif sampwidth == 4:
			return ('<f', 1.0)
		elif sampwidth == 8:
			return ('<d', 1.0)
		else:
			raise ValueError("Unknown sample size!")


class WaveFileReader(_WaveFileBase):
	"""Helper class to read samples from Wave file"""
	
	def __init__(self,filename):
		super().__init__()
		self._filename = filename
		self._wavefile = None
		self._channels = None
		self._samplewidth = None
		self._samplerate = None
	
	def __enter__(self):
		self._wavefile = wave.open(self._filename, 'rb')
		if self._wavefile:
			self._channels = self._wavefile.getnchannels()
			self._samplewidth =  self._wavefile.getsampwidth()
			self._samplerate = self._wavefile.getframerate()
		return self
	
	def __exit__(self, type, value, traceback):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		self._wavefile.close()
		self._wavefile = None
		self._channels = None
		self._samplewidth = None
		self._samplerate = None
	
	def __del__(self):
		if self._wavefile:
			print("RESOURCE LEAK: WaveFileReader object was not de-initialized properly!", file=sys.stderr)
			
	def getChannels(self):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		return self._channels
		
	def getSamplerate(self):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		return self._samplerate
		
	def getSampleWidth(self):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		return self._samplewidth
		
	def read(self, buffers):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		if len(buffers) < self._channels:
			raise RuntimeError("Number of buffers is insufficient!")
		frames = self._wavefile.readframes(self._minimum_buff_length(buffers))
		if frames:
			return self._unpack_samples(frames, buffers, self._channels, self._samplewidth)
		return None


class WaveFileWriter(_WaveFileBase):
	"""Helper class to write samples to Wave file"""
	
	def __init__(self,filename,channels,samplewidth,samplerate):
		super().__init__()
		self._filename = filename
		self._wavefile = None
		self._channels = channels
		self._samplewidth = samplewidth
		self._samplerate = samplerate
	
	def __enter__(self):
		self._wavefile = wave.open(self._filename, 'wb')
		if self._wavefile:
			self._wavefile.setnchannels(self._channels)
			self._wavefile.setsampwidth(self._samplewidth)
			self._wavefile.setframerate(self._samplerate)
		return self
	
	def __exit__(self, type, value, traceback):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		self._wavefile.close()
		self._wavefile = None
		self._channels = None
		self._samplewidth = None
		self._samplerate = None
	
	def __del__(self):
		if self._wavefile:
			print("RESOURCE LEAK: WaveFileWriter object was not de-initialized properly!", file=sys.stderr)
			
	def getChannels(self):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		return self._channels
		
	def getSamplerate(self):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		return self._samplerate
		
	def getSampleWidth(self):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		return self._samplewidth
		
	def write(self, buffers, length):
		if not self._wavefile:
			raise RuntimeError("Instance not initialized!")
		if len(buffers) < self._channels:
			raise RuntimeError("Number of buffers is insufficient!")
		if length < 1:
			raise RuntimeError("The given length value is zero!")
		if length > self._minimum_buff_length(buffers):
			raise RuntimeError("Length exceeds size of buffer!")
		samples = self._repack_samples(buffers, self._channels, self._samplewidth, length)
		if samples:
			return self._wavefile.writeframes(samples)
		return None


#----------------------------------------------------------------------
# Utility Functions
#----------------------------------------------------------------------

def alloc_sample_buffers(channles, length):
	buffers = ()
	for i in range(0, channles):
		arr = array.array('d')
		for j in range(0, length):
			arr.append(0.0)
		buffers += (arr,)
	return buffers


#----------------------------------------------------------------------
# Main
#----------------------------------------------------------------------

version = DynamicAudioNormalizer.getVersion()
print("Dynamic Audio Normalizer, Version {}.{}-{}".format(*version[0]))
print("Copyright (c) 2014-{} LoRd_MuldeR <mulder2@gmx.de>. Some rights reserved.".format(version[1][0][7:]))
print("Built on {} at {} with {} for Python-{}.\n".format(*version[1]))

if (len(sys.argv) < 3):
	print("Usage:\n  {} {} <input.wav> <output.wav>\n".format(os.path.basename(sys.executable), os.path.basename(__file__)), file=sys.stderr)
	sys.exit(1)

source_file =os.path.abspath(sys.argv[1])
output_file =os.path.abspath(sys.argv[2])

if not os.path.isfile(source_file):
	print("Input file \"{}\" not found!\n".format(source_file), file=sys.stderr)
	sys.exit(1)

print("Source file: \"{}\""  .format(source_file))
print("Output file: \"{}\"\n".format(output_file))

print("\nInitializing...", end = '', flush = True)
with WaveFileReader(source_file) as wav_reader:
	with WaveFileWriter(output_file, wav_reader.getChannels(), wav_reader.getSampleWidth(), wav_reader.getSamplerate()) as wav_writer:
		with DynamicAudioNormalizer(wav_reader.getChannels(), wav_reader.getSamplerate()) as normalizer:
			print(" Done!\n\nProcessing...", end = '', flush = True)
			buffers = alloc_sample_buffers(wav_reader.getChannels(), 4096)
			indicator = 0
			while True:
				count = wav_reader.read(buffers)
				if count:
					wav_writer.write(buffers, count)
					indicator += 1
					if indicator >= 7:
						print('.', end = '', flush = True)
						indicator = 0
					continue
				print(' Done!\n')
				break;